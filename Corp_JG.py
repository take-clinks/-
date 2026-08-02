import os
from flask import Flask, render_template_string, request
import google.generativeai as genai

app = Flask(__name__)

# Gemini APIキーのセットアップ
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

# 1. Web画面HTMLテンプレート（堅牢・デグレ防止CSS適用）
HTML = """




営業候補評価アプリ

body{font-family:sans-serif;background:#f8fafc;padding:16px;margin:0;}
.box{max-width:600px;margin:0 auto;background:#fff;padding:20px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1);}
h1{font-size:18px;text-align:center;margin-bottom:16px;color:#0f172a;}
label{display:block;margin-top:12px;font-weight:bold;font-size:14px;color:#334155;}
input[type=text]{width:100%;padding:10px;margin-top:4px;border:1px solid #cbd5e1;border-radius:4px;box-sizing:border-box;font-size:15px;}
button{width:100%;padding:12px;margin-top:16px;background:#2563eb;color:#fff;border:none;border-radius:4px;font-size:16px;font-weight:bold;cursor:pointer;}
button:disabled{background:#94a3b8;}
.res{margin-top:20px;padding:12px;background:#f1f5f9;border-radius:4px;white-space:pre-wrap;font-family:monospace;font-size:13px;line-height:1.6;border:1px solid #cbd5e1;}
.err{margin-top:16px;padding:10px;background:#fee2e2;color:#dc2626;border-radius:4px;font-size:13px;}




営業候補評価アプリ

1. 受注側会社名（自社等）

2. 取引先会社名（検討先）

営業可能性を評価する

{% if err %}{{err}}{% endif %}
{% if res %}{{res}}{% endif %}


"""

# 2. プロンプト定義（仕様書完全準拠）
PROMPT = """あなたは法人間取引の営業評価AIです。
以下の「受注側会社」と「取引先」について、公開情報を調査・分析し、指定の配点とフォーマットに従って営業適合度を評価してください。

■入力情報
受注側会社：{a}
取引先：{b}

■制約事項・ルール
1. 取引先の本社所在地を公開情報から確認し出力すること。確認できない場合は「確認できません」とすること。
2. 公開情報から確認できない内容は推測で補完しないこと。
3. 評価は「SES・システム開発評価」と「AIドリブン開発評価」の2区分を独立して各100点満点で評価すること（合算点・平均点は作成しない）。
4. 判定基準：
   - 80～100点：優先的に営業検討
   - 60～79点：有望
   - 40～59点：慎重に検討
   - 0～39点：営業優先度低め
5. 【最重要】理由文、自由コメント、アドバイス、追加確認事項等は一切出力しないこと。

■出力フォーマット（以下を厳格に再現すること）

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
公開情報の十分さ　　　　　　_　：[点数] / 5

合計：
[合計点] / 100

総合判定：
[総合判定文]"""

# 3. マルチモデル・自動フォールバック生成処理（404エラー完全防止）
def generate_with_fallback(prompt_text):
    candidate_models = [
        'gemini-1.5-flash-latest',
        'gemini-1.5-pro',
        'gemini-2.0-flash',
        'gemini-1.0-pro',
        'gemini-pro'
    ]
    
    last_error = None
    # 候補モデルを順次実行
    for model_name in candidate_models:
        try:
            m = genai.GenerativeModel(model_name)
            res = m.generate_content(prompt_text)
            if res and res.text:
                return res.text
        except Exception as e:
            last_error = e
            continue
            
    # 全候補失敗時、アカウントの全有効モデルから動的検索
    try:
        for m_info in genai.list_models():
            if 'generateContent' in m_info.supported_generation_methods:
                try:
                    m = genai.GenerativeModel(m_info.name)
                    res = m.generate_content(prompt_text)
                    if res and res.text:
                        return res.text
                except Exception:
                    continue
    except Exception as e:
        last_error = e

    raise last_error if last_error else Exception("利用可能なGeminiモデルが見つかりませんでした。")

# 4. Webルーティング処理
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        return render_template_string(HTML, a='', b='', res=None, err=None)
    
    a = request.form.get('company_a', '').strip()
    b = request.form.get('company_b', '').strip()
    
    if not a or not b:
        return render_template_string(HTML, a=a, b=b, res=None, err="両方の会社名を入力してください。")
    
    try:
        prompt_text = PROMPT.format(a=a, b=b)
        res_text = generate_with_fallback(prompt_text)
        return render_template_string(HTML, a=a, b=b, res=res_text, err=None)
    except Exception as e:
        return render_template_string(HTML, a=a, b=b, res=None, err=f"AI応答エラー: {str(e)}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
