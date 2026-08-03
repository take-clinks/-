import os

from flask import Flask, render_template_string, request, make_response
from google import genai

app = Flask(__name__)

# UI更新をブラウザへ確実に反映するため、バージョン番号だけ更新しています。
APP_VERSION = "2026-08-GEMINI-3-6-FLASH-INTERACTIONS-LOADING-v2"

# Google公式クイックスタートで確認した現在のモデル名。
# 自動探索・候補切替は行わず、この公式モデルだけを使用する。
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

    {% if res %}
      <div id="result-success" class="res">{{res}}</div>
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
        /*
         * required入力欄が空の場合はブラウザ標準の入力チェックを優先し、
         * 分析中UIへ変更しません。
         */
        if (!form.checkValidity()) {
          return;
        }

        /*
         * 二重クリック、連打、Enter連続入力による二重送信を防止します。
         */
        if (form.dataset.submitting === "true") {
          event.preventDefault();
          return;
        }

        form.dataset.submitting = "true";
        form.setAttribute("aria-busy", "true");

        /*
         * 送信は継続しつつ、UIだけを分析中状態へ変更します。
         */
        submitButton.disabled = true;
        submitButton.innerHTML =
          '<span class="spinner button-spinner" aria-hidden="true"></span>分析中です…';

        /*
         * disabled にするとPOST時に入力値が送信されないため、
         * readonly を使います。
         */
        if (companyAInput) {
          companyAInput.readOnly = true;
        }

        if (companyBInput) {
          companyBInput.readOnly = true;
        }

        loadingMessage.hidden = false;
        loadingMessage.setAttribute("aria-hidden", "false");

        /*
         * 2回目以降の検索時、前回の評価結果・エラー表示が
         * 画面に残ったまま分析中表示と同時に見えてしまう問題への対処。
         * 新しい結果はサーバーから返るHTML全体に含まれているため、
         * ここでは古い表示を一時的に隠すだけでよい。
         */
        const previousResult = document.getElementById("result-success");
        if (previousResult) {
          previousResult.hidden = true;
        }

        const previousError = document.getElementById("result-error");
        if (previousError) {
          previousError.hidden = true;
        }
      });

      /*
       * ブラウザの「戻る」操作などで画面が復元された場合、
       * ボタンが分析中のまま残らないように初期状態へ戻します。
       */
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
  max-width: 600px;
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

.res {
  margin-top: 20px;
  padding: 12px;
  background: #f1f5f9;
  border-radius: 4px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-family: monospace;
  font-size: 13px;
  line-height: 1.6;
  border: 1px solid #cbd5e1;
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
"""

PROMPT = """【最重要命令】すべての出力を「日本語」で行ってください。英語での出力は固く禁止します。
挨拶、前置き、思考プロセス、説明文などは一切出力せず、指定された出力フォーマットのみを直接出力してください。

あなたは法人間取引の営業評価AIです。
以下の「受注側会社」と「取引先」について公開情報を調査・分析し、指定の配点とフォーマットに従って営業適合度を日本語で評価してください。

■入力情報
受注側会社：{a}
取引先：{b}

■評価ルール・配点基準
1. 取引先の本社所在地を公開情報から確認し出力すること（確認できない場合は「確認できません」とすること）。
2. 公開情報から確認できない内容は推測で補完しないこと。
3. 評価は「SES・システム開発評価」と「AIドリブン開発評価」の2区分を独立して各100点満点で評価すること（合算点・平均点は作成しない）。
4. 総合判定の基準：
   - 80～100点：優先的に営業検討
   - 60～79点：有望
   - 40～59点：慎重に検討
   - 0～39点：営業優先度低め
5. 理由文、自由コメント、アドバイス、追加確認事項等は一切出力しないこと。

■出力フォーマット（以下の日本語フォーマットをそのまま出力すること）

取引先：
{b}

取引先本社所在地：
[所在地または確認できません]


【SES・システム開発評価】

受注側の商品・サービスとの適合度：[点数] / 25
取引先の事業規模・受注可能性　　：[点数] / 20
取引の継続性　　　　　　　　　　：[点数] / 15
売上拡大の可能性　　　　　　　　：[点数] / 15
戦略的メリット　　　　　　　　　：[点数] / 10
信用・支払面の安心度　　　　　　：[点数] / 10
公開情報の十分さ　　　　　　　　：[点数] / 5

合計：
[合計点] / 100

総合判定：
[総合判定文]


【AIドリブン開発評価】

受注側の商品・サービスとの適合度：[点数] / 25
取引先の事業規模・受注可能性　　：[点数] / 20
取引の継続性　　　　　　　　　　：[点数] / 15
売上拡大の可能性　　　　　　　　：[点数] / 15
戦略的メリット　　　　　　　　　：[点数] / 10
信用・支払面の安心度　　　　　　：[点数] / 10
公開情報の十分さ　　　　　　　　：[点数] / 5

合計：
[合計点] / 100

総合判定：
[総合判定文]"""

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
            res=None,
            err=None
        )

    a = request.form.get("company_a", "").strip()
    b = request.form.get("company_b", "").strip()

    if not a or not b:
        return build_html_response(
            a=a,
            b=b,
            res=None,
            err="両方の会社名を入力してください。"
        )

    try:
        prompt_text = PROMPT.format(a=a, b=b)
        result_text = generate_gemini_content(prompt_text)

        return build_html_response(
            a=a,
            b=b,
            res=result_text,
            err=None
        )

    except Exception as error:
        app.logger.exception("AI応答エラー")

        return build_html_response(
            a=a,
            b=b,
            res=None,
            err=f"AI応答エラー: {str(error)}"
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
    
