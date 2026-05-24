"""creview review-rounds シーケンサプログラム。

仕様: ``/creview:rounds`` スキル（plugin: creview）。

ラウンド単位で /creview:start -> /creview:triage -> /creview:respond ->
/creview:resolve を駆動し、未解決指摘がある間は内側ループ（最大 3 回）で
フィードバック再修正を試行する。ステップ 1 の初期化（ブランチ名取得 /
branch_dir 衝突回避）とステップ 3 の最終レポート生成も Instruction として
発行する。

agent-sequencer プラグイン（MCP サーバー）に依存する。本ファイルを
agent-sequencer の programs ディレクトリに配置して使用する。

収束判定:
  - findings_total == 0          -> Done
  - 当ラウンドでソースコード変更なし -> Done
  - confirm_round 有効で停止       -> Done
  - max_rounds 到達              -> Abort
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from agent_sequencer.api import Abort, Done, Instruction

NAME = "creview-rounds"
DESCRIPTION = (
    "creview プラグインの /creview:start / triage / respond / resolve スキルを使い、"
    "外側ループ（最大 N ラウンド）と内側ループ（フィードバック再修正、最大 3 回）を"
    "両方実装した完全版 review-rounds（最終レポート生成つき）。"
)

_DEFAULT_MAX_ROUNDS = 5
_DEFAULT_OUTPUT_BASE = ".claude/tmp"
_DEFAULT_FEEDBACK_ATTEMPTS = 3

PARAMS_SCHEMA = {
    "max_rounds": {
        "type": "integer",
        "default": _DEFAULT_MAX_ROUNDS,
        "minimum": 1,
        "maximum": 10,
        "description": "外側ループの最大ラウンド数（1〜10）",
    },
    "base": {
        "type": "string",
        "description": (
            "/creview:start に渡すベースブランチ。"
            "省略時はエージェント側で main / master を解決させる。"
        ),
    },
    "output_base": {
        "type": "string",
        "default": _DEFAULT_OUTPUT_BASE,
        "description": "レビュードキュメントの出力ベースディレクトリ",
    },
    "confirm": {
        "type": "boolean",
        "default": False,
        "description": (
            "True の場合、トリアージ / 見積がドキュメントへ永続化された後"
            "（respond フェーズの前）に、サマリを提示してユーザー確認を待つ"
            "（/creview:rounds --confirm 相当）。"
        ),
    },
    "confirm_round": {
        "type": "boolean",
        "default": False,
        "description": (
            "True の場合、ラウンド終了時に未解決指摘が残っていれば、"
            "次ラウンドへ進む前にユーザー確認を待つ"
            "（/creview:rounds --confirm-round 相当）。"
        ),
    },
    "commit": {
        "type": "boolean",
        "default": False,
        "description": (
            "True の場合、各指摘の修正後に集約 git commit を行う"
            "（/creview:respond --commit 相当）。"
        ),
    },
}

_START_SKILL = "/creview:start"
_TRIAGE_SKILL = "/creview:triage"
_RESPOND_SKILL = "/creview:respond"
_RESOLVE_SKILL = "/creview:resolve"

# 隣接バンドル: 最終レポートのマークダウンテンプレート。
# __file__ から解決するので plugin install 場所に依存しない絶対パスになる。
_FINAL_REPORT_FORMAT_PATH = (
    Path(__file__).resolve().parent / "review_rounds" / "final-report-format.md"
).as_posix()

# 隣接バンドル: 最終レポート編纂サブエージェント向けプロンプトテンプレート。
_FINAL_REPORT_COMPILE_PATH = (
    Path(__file__).resolve().parent / "review_rounds" / "final-report-compile.md"
).as_posix()

_SEVERITY_COUNTS_SCHEMA = {
    "type": "object",
    "properties": {
        "critical": {"type": "integer", "minimum": 0},
        "major": {"type": "integer", "minimum": 0},
        "minor": {"type": "integer", "minimum": 0},
        "info": {"type": "integer", "minimum": 0},
    },
    "additionalProperties": True,
}

_REVIEW_INIT_SCHEMA = {
    "type": "object",
    "properties": {
        "doc_path": {"type": "string", "minLength": 1},
        "branch_dir": {"type": "string", "minLength": 1},
        "findings_total": {"type": "integer", "minimum": 0},
        "severity_counts": _SEVERITY_COUNTS_SCHEMA,
    },
    "required": ["doc_path", "branch_dir", "findings_total"],
    "additionalProperties": True,
}

_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "doc_path": {"type": "string", "minLength": 1},
        "findings_total": {"type": "integer", "minimum": 0},
        "severity_counts": _SEVERITY_COUNTS_SCHEMA,
    },
    "required": ["doc_path", "findings_total"],
    "additionalProperties": True,
}

# /creview:triage 戻り値（トリアージ + 見積がドキュメントへ永続化される）
_TRIAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "will_fix_count": {"type": "integer", "minimum": 0},
        "wontfix_count": {"type": "integer", "minimum": 0},
        "maintain_count": {"type": "integer", "minimum": 0},
        "alternative_count": {"type": "integer", "minimum": 0},
        "downgrade_count": {"type": "integer", "minimum": 0},
        "summary_line": {"type": "string", "maxLength": 500},
    },
    "required": ["will_fix_count", "wontfix_count"],
    "additionalProperties": True,
}

# /creview:respond 戻り値（ステータスがドキュメントへ永続化される）
_RESPOND_SCHEMA = {
    "type": "object",
    "properties": {
        "fixed_count": {"type": "integer", "minimum": 0},
        "code_changed": {"type": "boolean"},
        "summary_line": {"type": "string", "maxLength": 500},
        "workflow_warning": {"type": ["string", "null"]},
    },
    "required": ["fixed_count", "code_changed"],
    "additionalProperties": True,
}

_RESOLVE_SCHEMA = {
    "type": "object",
    "properties": {
        "unresolved_count": {"type": "integer", "minimum": 0},
        "resolved_count": {"type": "integer", "minimum": 0},
        "feedback_count": {"type": "integer", "minimum": 0},
        "summary_line": {"type": "string", "maxLength": 500},
    },
    "required": ["unresolved_count"],
    "additionalProperties": True,
}

_FEEDBACK_SCHEMA = {
    "type": "object",
    "properties": {
        "unresolved_count": {"type": "integer", "minimum": 0},
        "resolved_count": {"type": "integer", "minimum": 0},
        "feedback_count": {"type": "integer", "minimum": 0},
        "code_changed": {"type": "boolean"},
        "summary_line": {"type": "string", "maxLength": 500},
        "workflow_warning": {"type": ["string", "null"]},
    },
    "required": ["unresolved_count", "code_changed"],
    "additionalProperties": True,
}

_USER_CONFIRM_SCHEMA = {
    "type": "object",
    "properties": {
        "proceed": {"type": "boolean"},
    },
    "required": ["proceed"],
    "additionalProperties": True,
}

_FINAL_REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "report_path": {"type": "string", "minLength": 1},
    },
    "required": ["report_path"],
    "additionalProperties": True,
}

# ----------------------------------------------------------------------
# Instruction テンプレート
# ----------------------------------------------------------------------
# format() で展開するため、JSON サンプルの { } は {{ }} でエスケープする。

_TPL_REVIEW_INIT = textwrap.dedent("""\
    [Round 1/{max_rounds} Step 2.1: review (初期化込み)]
    スキル: {skill}
    {base_clause} のブランチ差分に対して {skill} を実行する。
    オーケストレーター（あなた）はレビュー指摘本体を context に載せない。

    初期化:
    - 現在のブランチ名を取得する: git branch --show-current
    - branch_dir を決定する:
      - ブランチ名はディレクトリパスとして扱う（`/` を含みうる）
      - {output_base}/<branch> が既に存在する場合、{output_base}/<branch>_1,
        {output_base}/<branch>_2, ... と末尾に連番を付け、まだ存在しない最小の
        番号を採用する
      - 確定した「<branch> または <branch>_N」が branch_dir
    - 出力ディレクトリを mkdir -p で作成する: {output_base}/<branch_dir>/

    ファイル命名:
    - 本ラウンド (Round 1) の出力先: {output_base}/<branch_dir>/review-round1.md

    レビュードキュメントの言語: ユーザーのチャット言語。

    報告フォーマット (JSON):
    {{
      "doc_path": "<full path>",
      "branch_dir": "<branch_dir>",
      "findings_total": <int>,
      "severity_counts": {{"critical": <int>, "major": <int>, "minor": <int>, "info": <int>}}
    }}
    - branch_dir: 後続ラウンド + 最終レポートで一貫使用するため必ず報告すること
    - severity_counts: 集約サブエージェントの戻り値からそのまま転記\
""")

_TPL_REVIEW = textwrap.dedent("""\
    [Round {round_num}/{max_rounds} Step 2.1: review]
    スキル: {skill}
    {base_clause} のブランチ差分に対して {skill} を実行する。
    オーケストレーター（あなた）はレビュー指摘本体を context に載せない。

    ファイル命名規約:
    - 出力先: {output_base}/{branch_dir}/review-round{round_num}.md
    - branch_dir は Round 1 で確定した {branch_dir} を使用すること（連番再付与は禁止）

    レビュードキュメントの言語: ユーザーのチャット言語。

    収束誘導の防止:
    - 前ラウンドのレビュードキュメントはレビュアーに渡さないこと（バイアス回避）
    - 過去ラウンドの指摘件数 / 件数推移 / 「収束しつつある」等の傾向情報を
      レビュアーへのプロンプトに含めないこと
    - 過去ラウンドの指摘 ID（C-1 / M-1 等）や Fixed / Won't Fix 統計も含めないこと
    - 指摘件数を調整するためにテンプレートの一部を改変するのは禁止
    - レビューオーケストレーター自身が（レビュアー以外で）指摘を追加することは禁止

    報告フォーマット (JSON):
    {{
      "doc_path": "<full path>",
      "findings_total": <int>,
      "severity_counts": {{"critical": <int>, "major": <int>, "minor": <int>, "info": <int>}}
    }}\
""")

_TPL_TRIAGE = textwrap.dedent("""\
    [Round {round_num}/{max_rounds} Step 2.2: triage + estimate]
    スキル: {skill}
    レビュードキュメント {doc_path} の指摘をトリアージ・見積し、トリアージ /
    見積メタデータをドキュメントへ永続化する。オーケストレーター（あなた）は
    判定本文や指摘本体を context に載せない。本ステップでは修正は行わない。

    追加の制約:
    - トリアージサブエージェント起動時に previous_round_doc_paths 変数として
      下記を渡す（Round 1: (なし)、Round N: Round 1〜N-1 の doc_path）。
      判定挙動は triage スキルの templates/triage.md の Won't Fix ガイドライン参照:
{previous_round_doc_paths_block}
    - 見積サブエージェントには前ラウンドのレビュードキュメントを渡さない（バイアス回避）
    - トリアージサブエージェントの戻り値で Will Fix 件数を確認すること（0 件でも明示）
    - 拡散シグナル e（FIXME 起源の Will Fix）の判定では、対象指摘が
      レビュー本文または対象ファイルの FIXME: / TODO: を起点としているかを確認すること

    報告フォーマット (JSON):
    {{
      "will_fix_count": <int>,
      "wontfix_count": <int>,
      "maintain_count": <int>,
      "alternative_count": <int>,
      "downgrade_count": <int>,
      "summary_line": "(<=200 chars 1 行サマリ。見積編纂サブエージェントの戻り値をそのまま転記)"
    }}
    - will_fix_count / wontfix_count: トリアージサブエージェントの戻り値
    - maintain_count / alternative_count / downgrade_count: 見積編纂サブエージェントの戻り値
    - summary_line: ユーザー通知用の 1 行サマリ（リーダー context にはこの 1 行のみ載せる）\
""")

_TPL_CONFIRM_RESPOND = textwrap.dedent("""\
    [Round {round_num}/{max_rounds} Step 2.2.1: 修正前確認 (--confirm)]
    トリアージ / 見積はドキュメントへ永続化済み。{maintain} 件の Maintain /
    {alternative} 件の Alternative の修正に進む前に、見積サマリ summary_path を
    Read してユーザーに提示し、確認を待つ。

    報告フォーマット (JSON): {{"proceed": <bool>}}
    - proceed: true なら修正に進む / false ならここでラウンドを終了\
""")

_TPL_RESPOND = textwrap.dedent("""\
    [Round {round_num}/{max_rounds} Step 2.3: respond (修正 & 検証)]
    スキル: {skill}
    レビュードキュメント {doc_path} のうち、Estimate が ▶️ Maintain /
    🚧 Alternative の Will Fix 指摘を修正し、フォーマット&ビルド検証を実行し、
    ステータスをドキュメントへ永続化する。トリアージ / 見積は前ステップで
    永続化済み。オーケストレーター（あなた）は再実行ループのオーケストレーション
    のみ担当し、判定本文や指摘本体は context に載せない。
    {commit_clause}

    報告フォーマット (JSON):
    {{
      "fixed_count": <int>,
      "code_changed": <bool>,
      "summary_line": "(<=200 chars 1 行サマリ。編纂サブエージェントの戻り値をそのまま転記)",
      "workflow_warning": "(フォーマット／ビルド手順未宣言時の警告。無ければ null)"
    }}
    - fixed_count: 編纂サブエージェントの戻り値 fixed_count
      （Maintain の通常修正 + Alternative の FIXME 付与の合算 / 対象なしなら 0）
    - code_changed: 編纂サブエージェントの戻り値 code_changed
    - summary_line: ユーザー通知用の 1 行サマリ
    - workflow_warning: respond スキルがステップ 4 で保持した workflow_warning
      （フォーマット／ビルド手順が解決できず目視チェックのみだった場合に設定。
      解決できた場合は null）\
""")

_TPL_RESOLVE = textwrap.dedent("""\
    [Round {round_num}/{max_rounds} Step 2.4: resolve]
    スキル: {skill}
    レビュードキュメント {doc_path} の修正状況を検証する。オーケストレーター
    （あなた）は検証本文を context に載せない。

    報告フォーマット (JSON):
    {{
      "unresolved_count": <int>,
      "resolved_count": <int>,
      "feedback_count": <int>,
      "summary_line": "(<=200 chars 1 行サマリ。編纂サブエージェントの戻り値をそのまま転記)"
    }}
    - unresolved_count: 編纂サブエージェントの戻り値 feedback_count（Verification が 💬 Feedback のまま残っている指摘数）
    - resolved_count: 編纂サブエージェントの戻り値 resolved_count
    - feedback_count: unresolved_count と同義
    - summary_line: ユーザー通知用の 1 行サマリ\
""")

_TPL_FEEDBACK = textwrap.dedent("""\
    [Round {round_num}/{max_rounds} Step 2.5: フィードバック再修正 (試行 {attempt}/{max_attempts})]
    レビュードキュメント {doc_path} に 💬 Feedback のまま残っている指摘について、
    {triage_skill} -> {respond_skill} -> {resolve_skill} を 1 巡実施する。

    Step 2.5.{attempt}.1 フィードバックトリアージ + 見積
        {triage_skill} を実行する。
        トリアージプロンプトに追記: stage が "feedback" の指摘を優先的にトリアージする
        （Feedback 詳細は current_meta.verification にある）。
        見積プロンプトに追記: current_meta.verification の Feedback 内容を踏まえて見積。
        コストが膨らむ場合は Downgrade を検討。
        トリアージ起動時に previous_round_doc_paths 変数として下記を渡す
        （判定挙動は triage スキルの templates/triage.md の Won't Fix ガイドライン参照）:
{previous_round_doc_paths_block}

    Step 2.5.{attempt}.2 フィードバック修正
        {respond_skill} を実行する。
        修正プロンプトに追記: current_meta.verification の Feedback 内容を踏まえて再修正。
        Maintain / Alternative の対象がない場合はスキップして進む。

    Step 2.5.{attempt}.3 フィードバック検証
        {resolve_skill} を再実行する。

    報告フォーマット (JSON):
    {{
      "unresolved_count": <int>,
      "resolved_count": <int>,
      "feedback_count": <int>,
      "code_changed": <bool>,
      "summary_line": "(<=200 chars 1 行サマリ)",
      "workflow_warning": "(Step 2.5.2 の respond でフォーマット／ビルド手順未宣言時の警告。無ければ null)"
    }}
    - unresolved_count: 本試行後の {resolve_skill} 編纂サブエージェント戻り値 feedback_count
    - resolved_count: 同戻り値の resolved_count
    - feedback_count: unresolved_count と同義
    - code_changed: 本試行で 1 行でもソースコードを修正したか
    - summary_line: ユーザー通知用の 1 行サマリ
    - workflow_warning: Step 2.5.2 の {respond_skill} がステップ 4 で保持した
      workflow_warning（解決できた場合や respond をスキップした場合は null）\
""")

_TPL_CONFIRM_ROUND = textwrap.dedent("""\
    [Round {round_num}/{max_rounds} Step 2.6: 次ラウンド確認 (--confirm-round)]
    未解決の指摘が {unresolved} 件残った状態でラウンドを終了する。
    次のラウンド (Round {next_round}/{max_rounds}) に進むかをユーザーに確認する。

    報告フォーマット (JSON): {{"proceed": <bool>}}
    - proceed: true なら次ラウンドへ進む / false ならここで終了\
""")

_TPL_FINAL_REPORT = textwrap.dedent("""\
    [Step 3: 最終レポート生成（最終レポート編纂サブエージェントへ委譲）]
    全 {rounds_executed} ラウンドを終了した。最終レポート編纂サブエージェントに
    委譲して最終レポートを生成する。

    出力先: {output_base}/{branch_dir}/final-report.md
    終了理由: {termination_reason}

    各ラウンドのレビュードキュメント:
{round_docs_block}

    各ラウンドの統計（参考データ）:
{per_round_stats_block}

    `Agent(subagent_type="review-helper", prompt=...)` でサブエージェントを
    起動する（model は review-helper の agent 定義に従う、リーダーから
    model 指定はしない）。起動プロンプトは以下:

    ```
    最初の行動として `{compile_path}` を必ず Read する。Read 完了前に他の判断・行動・ツール呼び出しを行わない。Read 後はその指示に従う。

    変数（テンプレート中の {{{{...}}}} placeholder を置換）:
    - round_doc_paths: |
{round_docs_block}
    - round_stats: |
{per_round_stats_block}
    - template_path: {format_path}
    - report_path: {output_base}/{branch_dir}/final-report.md
    - language: ユーザーのチャット言語

    追加情報:
    - 終了理由: {termination_reason}

    ラウンド固有のオーバーライド（テンプレートの指示に従った後に適用）:
    - (該当なし)

    戻り値に `template_id`（テンプレートの frontmatter から Read した値）を含める。リーダーは戻り値の template_id が `4f8a2d1c-9b35-4e67-a2c1-8b5d3f9e7a16` と一致することを確認すること。
    ```

    報告フォーマット (JSON): {{"report_path": "<full path>"}}\
""")


def _format_round_docs_block(round_records: list[dict]) -> str:
    """各ラウンドの doc_path をリスト形式で書き出す。"""
    if not round_records:
        return "    (なし)"
    return "\n".join(
        f"    - Round {r['round_num']}: {r['doc_path']}"
        for r in round_records
    )


def _format_per_round_stats_block(round_records: list[dict]) -> str:
    """各ラウンドの統計を 1 行ずつ書き出す（最終レポート生成の根拠データ）。"""
    if not round_records:
        return "    (なし)"
    lines: list[str] = []
    for r in round_records:
        sev = r.get("severity_counts") or {}
        sev_str = (
            f"crit={sev.get('critical', 0)},maj={sev.get('major', 0)},"
            f"min={sev.get('minor', 0)},info={sev.get('info', 0)}"
        )
        line = (
            f"    - Round {r['round_num']}: "
            f"findings={r['findings_total']} ({sev_str}), "
            f"will_fix={r['will_fix_count']}, "
            f"maintain={r.get('maintain_count', 0)}, "
            f"alternative={r.get('alternative_count', 0)}, "
            f"downgrade={r.get('downgrade_count', 0)}, "
            f"fixed={r['fixed_count']}, "
            f"wontfix={r['wontfix_count']}, "
            f"resolved={r.get('resolved_count', 0)}, "
            f"feedback_attempts={r['feedback_attempts']}, "
            f"unresolved={r['unresolved']}, "
            f"code_changed={r['code_changed']}"
        )
        warning = r.get("workflow_warning")
        if warning:
            line += f', workflow_warning="{warning}"'
        lines.append(line)
    return "\n".join(lines)


def run(ctx):
    """ラウンドループを駆動するシーケンサプログラム本体。"""
    max_rounds = ctx.params.get("max_rounds", _DEFAULT_MAX_ROUNDS)
    base = ctx.params.get("base")
    output_base = ctx.params.get("output_base", _DEFAULT_OUTPUT_BASE)
    confirm = ctx.params.get("confirm", False)
    confirm_round = ctx.params.get("confirm_round", False)
    commit = ctx.params.get("commit", False)

    base_clause = (
        f"ベースブランチ {base}"
        if base
        else "デフォルトのベースブランチ (main または master)"
    )
    commit_clause = (
        "オプション: --commit を有効化（修正後に集約 git commit を行う）。"
        if commit
        else "オプション: --commit は無効（コミットしない）。"
    )

    branch_dir: str | None = None
    round_records: list[dict] = []
    converged = False
    termination_reason: str | None = None

    for round_num in range(1, max_rounds + 1):
        ctx.publish_progress(
            current=round_num,
            of=max_rounds,
            label=f"Round {round_num}/{max_rounds}",
        )

        # ----- Step 2.1: review (/creview:start) -----
        # Round 1: 初期化込みテンプレートで branch_dir を確定させる
        # Round 2+: 確定済み branch_dir を渡して再利用する
        if round_num == 1:
            review_result = yield Instruction(
                text=_TPL_REVIEW_INIT.format(
                    max_rounds=max_rounds,
                    skill=_START_SKILL,
                    base_clause=base_clause,
                    output_base=output_base,
                ),
                expect_schema=_REVIEW_INIT_SCHEMA,
                timeout_minutes=60,
            )
            branch_dir = review_result["branch_dir"]
        else:
            review_result = yield Instruction(
                text=_TPL_REVIEW.format(
                    round_num=round_num,
                    max_rounds=max_rounds,
                    skill=_START_SKILL,
                    base_clause=base_clause,
                    output_base=output_base,
                    branch_dir=branch_dir,
                ),
                expect_schema=_REVIEW_SCHEMA,
                timeout_minutes=60,
            )

        doc_path = review_result["doc_path"]
        findings_total = review_result["findings_total"]

        round_record = {
            "round_num": round_num,
            "doc_path": doc_path,
            "findings_total": findings_total,
            "severity_counts": review_result.get("severity_counts") or {},
            "will_fix_count": 0,
            "fixed_count": 0,
            "wontfix_count": 0,
            "maintain_count": 0,
            "alternative_count": 0,
            "downgrade_count": 0,
            "resolved_count": 0,
            "feedback_attempts": 0,
            "unresolved": 0,
            "code_changed": False,
            "respond_summary_line": "",
            "resolve_summary_line": "",
            "workflow_warning": None,
        }

        # ----- 収束判定 1: 指摘ゼロ -----
        if findings_total == 0:
            round_records.append(round_record)
            converged = True
            termination_reason = "指摘ゼロで収束"
            break

        # ----- Step 2.2: triage + estimate (/creview:triage) -----
        # round_records は本ラウンドを append する前なので、
        # この時点の中身が「過去ラウンドのドキュメント一覧」になる。
        triage_result = yield Instruction(
            text=_TPL_TRIAGE.format(
                round_num=round_num,
                max_rounds=max_rounds,
                skill=_TRIAGE_SKILL,
                doc_path=doc_path,
                previous_round_doc_paths_block=_format_round_docs_block(
                    round_records
                ),
            ),
            expect_schema=_TRIAGE_SCHEMA,
            timeout_minutes=120,
        )

        round_record["will_fix_count"] = triage_result["will_fix_count"]
        round_record["wontfix_count"] = triage_result["wontfix_count"]
        round_record["maintain_count"] = triage_result.get("maintain_count", 0)
        round_record["alternative_count"] = triage_result.get(
            "alternative_count", 0
        )
        round_record["downgrade_count"] = triage_result.get("downgrade_count", 0)
        round_record["respond_summary_line"] = triage_result.get(
            "summary_line", ""
        )

        fixable = (
            round_record["maintain_count"] + round_record["alternative_count"]
        )

        # ----- 修正前確認 (--confirm + 修正対象あり) -----
        if confirm and fixable > 0:
            confirm_result = yield Instruction(
                text=_TPL_CONFIRM_RESPOND.format(
                    round_num=round_num,
                    max_rounds=max_rounds,
                    maintain=round_record["maintain_count"],
                    alternative=round_record["alternative_count"],
                ),
                expect_schema=_USER_CONFIRM_SCHEMA,
                timeout_minutes=60,
            )
            if not confirm_result["proceed"]:
                round_records.append(round_record)
                termination_reason = "ユーザー指示によりラウンドループを停止"
                break

        # fixable == 0（全件 Won't Fix / Downgrade）なら respond / resolve をスキップ
        if fixable > 0:
            # ----- Step 2.3: respond (/creview:respond) -----
            respond_result = yield Instruction(
                text=_TPL_RESPOND.format(
                    round_num=round_num,
                    max_rounds=max_rounds,
                    skill=_RESPOND_SKILL,
                    doc_path=doc_path,
                    commit_clause=commit_clause,
                ),
                expect_schema=_RESPOND_SCHEMA,
                timeout_minutes=180,
            )
            round_record["fixed_count"] = respond_result["fixed_count"]
            round_record["code_changed"] = respond_result["code_changed"]
            if respond_result.get("summary_line"):
                round_record["respond_summary_line"] = respond_result[
                    "summary_line"
                ]
            if respond_result.get("workflow_warning"):
                round_record["workflow_warning"] = respond_result[
                    "workflow_warning"
                ]

            # fixed_count == 0 なら検証対象がないので Step 2.4-2.5 はスキップ
            if respond_result["fixed_count"] > 0:
                # ----- Step 2.4: resolve (/creview:resolve) -----
                resolve_result = yield Instruction(
                    text=_TPL_RESOLVE.format(
                        round_num=round_num,
                        max_rounds=max_rounds,
                        skill=_RESOLVE_SKILL,
                        doc_path=doc_path,
                    ),
                    expect_schema=_RESOLVE_SCHEMA,
                    timeout_minutes=30,
                )
                round_record["unresolved"] = resolve_result["unresolved_count"]
                round_record["resolved_count"] = resolve_result.get(
                    "resolved_count", 0
                )
                round_record["resolve_summary_line"] = resolve_result.get(
                    "summary_line", ""
                )

                # ----- Step 2.5: 内側ループ — フィードバック再修正（最大 3 回） -----
                for attempt in range(1, _DEFAULT_FEEDBACK_ATTEMPTS + 1):
                    if round_record["unresolved"] == 0:
                        break

                    ctx.publish_progress(
                        current=round_num,
                        of=max_rounds,
                        label=(
                            f"Round {round_num}/{max_rounds} - "
                            f"feedback attempt {attempt}/{_DEFAULT_FEEDBACK_ATTEMPTS}"
                        ),
                    )

                    feedback_result = yield Instruction(
                        text=_TPL_FEEDBACK.format(
                            round_num=round_num,
                            max_rounds=max_rounds,
                            attempt=attempt,
                            max_attempts=_DEFAULT_FEEDBACK_ATTEMPTS,
                            doc_path=doc_path,
                            triage_skill=_TRIAGE_SKILL,
                            respond_skill=_RESPOND_SKILL,
                            resolve_skill=_RESOLVE_SKILL,
                            previous_round_doc_paths_block=_format_round_docs_block(
                                round_records
                            ),
                        ),
                        expect_schema=_FEEDBACK_SCHEMA,
                        timeout_minutes=120,
                    )
                    round_record["feedback_attempts"] += 1
                    round_record["unresolved"] = feedback_result["unresolved_count"]
                    if "resolved_count" in feedback_result:
                        round_record["resolved_count"] = feedback_result[
                            "resolved_count"
                        ]
                    if feedback_result.get("summary_line"):
                        round_record["resolve_summary_line"] = feedback_result[
                            "summary_line"
                        ]
                    if feedback_result.get("workflow_warning"):
                        round_record["workflow_warning"] = feedback_result[
                            "workflow_warning"
                        ]
                    if feedback_result["code_changed"]:
                        round_record["code_changed"] = True

        round_records.append(round_record)

        # ----- 収束判定 2: ソースコード変更なし -----
        if not round_record["code_changed"]:
            converged = True
            termination_reason = "ソースコード変更なしで収束"
            break

        # ----- 次ラウンド確認 (--confirm-round + 未解決あり + 次ラウンドが残っている) -----
        if confirm_round and round_record["unresolved"] > 0 and round_num < max_rounds:
            confirm_result = yield Instruction(
                text=_TPL_CONFIRM_ROUND.format(
                    round_num=round_num,
                    max_rounds=max_rounds,
                    next_round=round_num + 1,
                    unresolved=round_record["unresolved"],
                ),
                expect_schema=_USER_CONFIRM_SCHEMA,
                timeout_minutes=60,
            )
            if not confirm_result["proceed"]:
                termination_reason = "ユーザー指示によりラウンドループを停止"
                break
    else:
        # for/else: break しなかった = max_rounds 到達
        termination_reason = f"最大ラウンド数 {max_rounds} に到達"

    # ----- Step 3: 最終レポート生成 -----
    report_path: str | None = None
    if branch_dir is not None and round_records:
        report_result = yield Instruction(
            text=_TPL_FINAL_REPORT.format(
                rounds_executed=len(round_records),
                output_base=output_base,
                branch_dir=branch_dir,
                termination_reason=termination_reason,
                format_path=_FINAL_REPORT_FORMAT_PATH,
                compile_path=_FINAL_REPORT_COMPILE_PATH,
                round_docs_block=_format_round_docs_block(round_records),
                per_round_stats_block=_format_per_round_stats_block(round_records),
            ),
            expect_schema=_FINAL_REPORT_SCHEMA,
            timeout_minutes=30,
        )
        report_path = report_result["report_path"]

    # ----- 累計集計 -----
    total_will_fix = sum(r["will_fix_count"] for r in round_records)
    total_fixed = sum(r["fixed_count"] for r in round_records)
    total_wontfix = sum(r["wontfix_count"] for r in round_records)
    total_maintain = sum(r.get("maintain_count", 0) for r in round_records)
    total_alternative = sum(r.get("alternative_count", 0) for r in round_records)
    total_downgrade = sum(r.get("downgrade_count", 0) for r in round_records)
    total_resolved = sum(r.get("resolved_count", 0) for r in round_records)
    total_feedback_attempts = sum(r["feedback_attempts"] for r in round_records)
    last_unresolved = round_records[-1]["unresolved"] if round_records else 0

    summary = {
        "rounds_executed": len(round_records),
        "converged": converged,
        "reason": termination_reason,
        "branch_dir": branch_dir,
        "report_path": report_path,
        "total_will_fix": total_will_fix,
        "total_fixed": total_fixed,
        "total_wontfix": total_wontfix,
        "total_maintain": total_maintain,
        "total_alternative": total_alternative,
        "total_downgrade": total_downgrade,
        "total_resolved": total_resolved,
        "total_feedback_attempts": total_feedback_attempts,
        "last_unresolved": last_unresolved,
        "round_records": round_records,
    }

    if converged or termination_reason == "ユーザー指示によりラウンドループを停止":
        yield Done(summary=summary)
    else:
        yield Abort(
            reason=(
                f"{termination_reason}（収束しませんでした）。"
                f"累計 will_fix={total_will_fix}, fixed={total_fixed}, "
                f"wontfix={total_wontfix}, feedback_attempts={total_feedback_attempts}、"
                f"最終ラウンドの未解決={last_unresolved}。"
                f"最終レポート: {report_path or '(未生成)'}。"
                "max_rounds を増やすか、未解決指摘を確認してください。"
            )
        )
