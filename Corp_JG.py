import os
import json
import re

from flask import Flask, render_template_string, request, make_response
from google import genai

app = Flask(__name__)

APP_VERSION = "2026-08-GEMINI-3-6-FLASH-JSON-TABLE-TOKEN-SAVE-v1"

GEMINI_MODEL = "gemini-3.6-flash"

api_key = os.environ.get("GEMINI_API_KEY")

gemini_client = None

if api_key:
    gemini_client = genai.Client(api_key=api_key)

RAW_HTML = """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="app-version" content="{{app_version}}">
  <title>営業候補評価アプリ</title>
  <link rel="stylesheet" href="/assets/app.css?v={{app_version}}">
</head>
<body>
  <main class="box">
    <h1>営業候補評価アプリ</h1>

    <form id="evaluation-form" method="POST" action="/">
      <label for="company_a">1. 受注側会社名（自社等）</label>
      <input
        id="company_a"
        type="text"
        name="company_a"
        value="{{a}}"
        required
        placeholder="例: 株式会社〇〇"
      >

      <label for="company_b">2. 取引先会社名（検討先）</label>
      <input
        id="company_b"
        type="text"
        name="company_b"
        value="{{b}}"
        required
        placeholder="例: 株式会社△△"
      >

      <button id="submit-button" type="submit">
        営業可能性を評価する
      </button>

      <div
        id="loading-message"
        class="loading"
        role="status"
        aria-live="polite"
        aria-hidden="true"
        hidden
      >
        <span class="spinner" aria-hidden="true"></span>
        <span>
          Geminiで企業情報を分析・評価しています。<br>
          評価結果が表示されるまで、しばらくお待ちください。
        </span>
      </div>
    </form>

    {% if err %}
      <div id="result-error" class="err">{{err}}</div>
    {% endif %}

    {% if result %}
      <div id="result-success" class="result-wrap">

        <div class="company-info">
          <div class="company-info-row">
            <span class="company-info-label">取引先</span>
            <span class="company-info-value">{{result.company_b}}</span>
          </div>
          <div class="company-info-row">
            <span class="company-info-label">本社所在地</span>
            <span class="company-info-value">{{result.headquarters}}</span>
          </div>
        </div>

        <div class="eval-grid">

          <div class="eval-card">
            <h2 class="eval-title">SES・システム開発評価</h2>
            <table class="eval-table">
              <tbody>
                <tr><td>商品・サービス適合度</td><td>{{result.ses.fit}} / 25</td></tr>
                <tr><td>事業規模・受注可能性</td><td>{{result.ses.scale}} / 20</td></tr>
                <tr><td>取引の継続性</td><td>{{result.ses.continuity}} / 15</td></tr>
                <tr><td>売上拡大の可能性</td><td>{{result.ses.growth}} / 15</td></tr>
                <tr><td>戦略的メリット</td><td>{{result.ses.strategy}} / 10</td></tr>
                <tr><td>信用・支払面の安心度</td><td>{{result.ses.trust}} / 10</td></tr>
                <tr><td>公開情報の十分さ</td><td>{{result.ses.info}} / 5</td></tr>
                <tr class="total-row"><td>合計</td><td>{{result.ses.total}} / 100</td></tr>
              </tbody>
            </table>
            <div class="judgement-badge judgement-{{result.ses.level}}">
              総合判定：{{result.ses.judgement}}
            </div>
          </div>

          <div class="eval-card">
            <h2 class="eval-title">AIドリブン開発評価</h2>
            <table class="eval-table">
              <tbody>
                <tr><td>商品・サービス適合度</td><td>{{result.ai.fit}} / 25</td></tr>
                <tr><td>事業規模・受注可能性</td><td>{{result.ai.scale}} / 20</td></tr>
                <tr><td>取引の継続性</td><td>{{result.ai.continuity}} / 15</td></tr>
                <tr><td>売上拡大の可能性</td><td>{{result.ai.growth}} / 15</td></tr>
                <tr><td>戦略的メリット</td><td>{{result.ai.strategy}} / 10</td></tr>
                <tr><td>信用・支払面の安心度</td><td>{{result.ai.trust}} / 10</td></tr>
                <tr><td>公開情報の十分さ</td><td>{{result.ai.info}} / 5</td></tr>
                <tr class="total-row"><td>合計</td><td>{{result.ai.total}} / 100</td></tr>
              </tbody>
            </table>
            <div class="judgement-badge judgement-{{result.ai.level}}">
              総合判定：{{result.ai.judgement}}
            </div>
          </div>

        </div>
      </div>
    {% endif %}
  </main>

  <script>
    (function () {
      const form = document.getElementById("evaluation-form");
      const submitButton = document.getElementById("submit-button");
      const loadingMessage = document.getElementById("loading-message");
      const companyAInput = document.getElementById("company_a");
      const companyBInput = document.getElementById("company_b");

      if (!form || !submitButton || !loadingMessage) {
        return;
      }

      form.addEventListener("submit", function (event) {
        if (!form.checkValidity()) {
          return;
        }

        if (form.dataset.submitting === "true") {
          event.preventDefault();
          return;
        }

        form.dataset.submitting = "true";
        form.setAttribute("aria-busy", "true");

        submitButton.disabled = true;
        submitButton.innerHTML =
          '<span class="spinner button-spinner" aria-hidden="true"></span>分析中です…';

        if (companyAInput) {
          companyAInput.readOnly = true;
        }

        if (companyBInput) {
          companyBInput.readOnly = true;
        }

        loadingMessage.hidden = false;
        loadingMessage.setAttribute("aria-hidden", "false");

        const previousResult = document.getElementById("result-success");
        if (previousResult) {
          previousResult.hidden = true;
        }

        const previousError = document.getElementById("result-error");
        if (previousError) {
          previousError.hidden = true;
        }
      });

      window.addEventListener("pageshow", function () {
        form.dataset.submitting = "false";
        form.removeAttribute("aria-busy");

        submitButton.disabled = false;
        submitButton.textContent = "営業可能性を評価する";

        if (companyAInput) {
          companyAInput.readOnly = false;
        }

        if (companyBInput) {
          companyBInput.readOnly = false;
        }

        loadingMessage.hidden = true;
        loadingMessage.setAttribute("aria-hidden", "true");

        const previousResult = document.getElementById("result-success");
        if (previousResult) {
          previousResult.hidden = false;
        }

        const previousError = document.getElementById("result-error");
        if (previousError) {
          previousError.hidden = false;
        }
      });
    })();
  </script>
</body>
</html>"""

CSS = """body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: #f8fafc;
  color: #1e293b;
  padding: 16px;
  margin: 0;
}

.box {
  max-width: 900px;
  margin: 0 auto;
  background: #ffffff;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

h1 {
  font-size: 18px;
  text-align: center;
  margin: 0 0 16px;
  color: #0f172a;
}

label {
  display: block;
  margin-top: 12px;
  font-weight: bold;
  font-size: 14px;
  color: #334155;
}

input[type="text"] {
  width: 100%;
  padding: 10px;
  margin-top: 4px;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  box-sizing: border-box;
  font-size: 15px;
}

input[type="text"]:read-only {
  background: #f8fafc;
  color: #475569;
  cursor: wait;
}

button {
  width: 100%;
  padding: 12px;
  margin-top: 16px;
  background: #2563eb;
  color: #ffffff;
  border: none;
  border-radius: 4px;
  font-size: 16px;
  font-weight: bold;
  cursor: pointer;
}

button:hover {
  background: #1d4ed8;
}

button:disabled {
  background: #94a3b8;
  cursor: wait;
}

.loading {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-top: 12px;
  padding: 12px;
  background: #eff6ff;
  color: #1d4ed8;
  border: 1px solid #bfdbfe;
  border-radius: 4px;
  font-size: 13px;
  line-height: 1.6;
}

.loading[hidden] {
  display: none;
}

.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  flex: 0 0 16px;
  border: 2px solid rgba(37, 99, 235, 0.25);
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.button-spinner {
  width: 14px;
  height: 14px;
  flex: none;
  margin-right: 8px;
  vertical-align: -2px;
  border-color: rgba(255, 255, 255, 0.4);
  border-top-color: #ffffff;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.err {
  margin-top: 16px;
  padding: 10px;
  background: #fee2e2;
  color: #dc2626;
  border-radius: 4px;
  font-size: 13px;
  line-height: 1.6;
}

.result-wrap {
  margin-top: 20px;
}

.company-info {
  background: #f1f5f9;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 12px 16px;
  margin-bottom: 16px;
}

.company-info-row {
  display: flex;
  gap: 8px;
  font-size: 14px;
  padding: 2px 0;
}

.company-info-label {
  font-weight: bold;
  color: #334155;
  flex: 0 0 90px;
}

.company-info-value {
  color: #0f172a;
}

.eval-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

@media (max-width: 640px) {
  .eval-grid {
    grid-template-columns: 1fr;
  }
}

.eval-card {
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 12px;
  background: #ffffff;
}

.eval-title {
  font-size: 14px;
  margin: 0 0 8px;
  color: #0f172a;
  border-bottom: 2px solid #2563eb;
  padding-bottom: 6px;
}

.eval-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.eval-table td {
  padding: 6px 4px;
  border-bottom: 1px solid #e2e8f0;
}

.eval-table td:last-child {
  text-align: right;
  white-space: nowrap;
  font-weight: bold;
  width: 70px;
}

.eval-table .total-row td {
  border-top: 2px solid #94a3b8;
  border-bottom: none;
  font-size: 14px;
  padding-top: 8px;
}

.judgement-badge {
  margin-top: 10px;
  padding: 8px 10px;
  border-radius: 4px;
  font-size: 13px;
  font-weight: bold;
  text-align: center;
}

.judgement-high {
  background: #dcfce7;
  color: #166534;
  border: 1px solid #86efac;
}

.judgement-mid-high {
  background: #dbeafe;
  color: #1e40af;
  border: 1px solid #93c5fd;
}

.judgement-mid-low {
  background: #fef9c3;
  color: #854d0e;
  border: 1px solid #fde047;
}

.judgement-low {
  background: #fee2e2;
  color: #991b1b;
  border: 1px solid #fca5a5;
}
"""

# トークン削減版PROMPT。
# ・説明文を短縮
# ・判定基準の説明を削除（Python側で必ず再計算・上書きするため不要）
# ・JSON構造は維持（データ取得に必須のため削らない）
PROMPT = """法人間取引の営業評価AIとして、下記2社を公開情報のみで評価し、
JSON構造のみを出力してください。説明文・前置き・コードブロック記号は禁止。
値がすべて日本語。推測で補完しない。

受注側：{a}
取引先：{b}

配点（各区分100点満点、SES区分とAI区分は独立evaluate）：
fit25 scale20 continuity15 growth15 strategy10 trust10 info5

出力JSON：
{{
  "headquarters": "取引先本社所在地。不明なら確認できません",
  "ses": {{"fit":0,"scale":0,"continuity":0,"growth":0,"strategy":0,"trust":0,"info":0,"total":0,"judgement":""}},
  "ai": {{"fit":0,"scale":0,"continuity":0,"growth":0,"strategy":0,"trust":0,"info":0,"total":0,"judgement":""}}
}}"""

def strip_code_fence(text):
    stripped = text.strip()
    stripped = re.sub(r"^```[a-zA-Z]*\s*", "", stripped)
    stripped = re.sub(r"```\s*$", "", stripped)
    return stripped.strip()


def judgement_level(total):
    if total >= 80:
        return "high"
    if total >= 60:
        return "mid-high"
    if total >= 40:
        return "mid-low"
    return "low"


def judgement_text(total):
    if total >= 80:
        return "優先的に営業検討"
    if total >= 60:
        return "有望"
    if total >= 40:
        return "慎重に検討"
    return "営業優先度低め"


def normalize_section(section):
    def to_int(value):
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return 0

    fit = to_int(section.get("fit"))
    scale = to_int(section.get("scale"))
    continuity = to_int(section.get("continuity"))
    growth = to_int(section.get("growth"))
    strategy = to_int(section.get("strategy"))
    trust = to_int(section.get("trust"))
    info = to_int(section.get("info"))

    calculated_total = fit + scale + continuity + growth + strategy + trust + info

    if calculated_total > 100:
        calculated_total = 100
    if calculated_total < 0:
        calculated_total = 0

    return {
        "fit": fit,
        "scale": scale,
        "continuity": continuity,
        "growth": growth,
        "strategy": strategy,
        "trust": trust,
        "info": info,
        "total": calculated_total,
        "judgement": judgement_text(calculated_total),
        "level": judgement_level(calculated_total),
    }


def parse_gemini_json(raw_text):
    cleaned = strip_code_fence(raw_text)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Geminiの応答をJSONとして解析できませんでした。"
        ) from error

    if "ses" not in data or "ai" not in data:
        raise RuntimeError(
            "Geminiの応答に必要な評価データ（ses/ai）が含まれていません。"
        )

    headquarters = data.get("headquarters")
    if not isinstance(headquarters, str) or not headquarters.strip():
        headquarters = "確認できません"

    return {
        "headquarters": headquarters,
        "ses": normalize_section(data["ses"]),
        "ai": normalize_section(data["ai"]),
    }


def generate_gemini_content(prompt_text):
    if gemini_client is None:
        raise RuntimeError(
            "GEMINI_API_KEY が設定されていません。"
            "RenderのEnvironmentを確認してください。"
        )

    try:
        app.logger.warning(
            "Gemini Interactions API試行: モデル=%s",
            GEMINI_MODEL
        )

        interaction = gemini_client.interactions.create(
            model=GEMINI_MODEL,
            input=prompt_text
        )

        result_text = getattr(interaction, "output_text", "") or ""

        if not result_text.strip():
            raise RuntimeError(
                "Gemini APIから評価結果テキストを取得できませんでした。"
            )

        app.logger.warning(
            "Gemini Interactions API応答成功: モデル=%s",
            GEMINI_MODEL
        )

        return result_text.strip()

    except Exception as error:
        error_text = str(error)

        app.logger.exception(
            "Gemini Interactions API呼び出し失敗: モデル=%s",
            GEMINI_MODEL
        )

        if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
            raise RuntimeError(
                "Gemini無料枠の回数またはトークン上限に達しました。"
                "少し待ってから再実行してください。"
            ) from error

        if "404" in error_text or "NOT_FOUND" in error_text:
            raise RuntimeError(
                "Geminiモデルが利用できません。"
                "Render LogsでGemini Interactions APIのエラー内容を確認してください。"
            ) from error

        raise RuntimeError(
            "Gemini API呼び出し中にエラーが発生しました。"
            f"詳細: {error_text}"
        ) from error


def build_html_response(**kwargs):
    rendered = render_template_string(
        RAW_HTML,
        app_version=APP_VERSION,
        **kwargs
    )

    response = make_response(rendered, 200)
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    response.headers["X-App-Version"] = APP_VERSION

    return response


@app.route("/assets/app.css", methods=["GET"])
def app_css():
    response = make_response(CSS, 200)
    response.headers["Content-Type"] = "text/css; charset=utf-8"
    response.headers["Cache-Control"] = "public, max-age=300"
    response.headers["X-App-Version"] = APP_VERSION

    return response


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return build_html_response(
            a="",
            b="",
            result=None,
            err=None
        )

    a = request.form.get("company_a", "").strip()
    b = request.form.get("company_b", "").strip()

    if not a or not b:
        return build_html_response(
            a=a,
            b=b,
            result=None,
            err="両方の会社名を入力してください。"
        )

    try:
        prompt_text = PROMPT.format(a=a, b=b)
        raw_result_text = generate_gemini_content(prompt_text)
        parsed_result = parse_gemini_json(raw_result_text)
        parsed_result["company_b"] = b

        return build_html_response(
            a=a,
            b=b,
            result=parsed_result,
            err=None
        )

    except Exception as error:
        app.logger.exception("AI応答エラー")

        return build_html_response(
            a=a,
            b=b,
            result=None,
            err=f"AI応答エラー: {str(error)}"
        )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
