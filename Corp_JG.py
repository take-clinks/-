import os
from flask import Flask, render_template_string, request, Response
import google.generativeai as genai

app = Flask(__name__)

# Gemini APIの初期化
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

# Web画面HTML（自動翻訳・文字化け完全防止構造）
RAW_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>営業候補評価アプリ</title>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f8fafc;color:#1e293b;padding:16px;margin:0;}
.box{max-width:600px;margin:0 auto;background:#fff;padding:20px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1);}
h1{font-size:18px;text-align:center;margin-bottom:16px;color:#0f172a;}
label{display:block;margin-top:12px;font-weight:bold;font-size:14px;color:#334155;}
input[type=text]{width:100%;padding:10px;margin-top:4px;border:1px solid #cbd5e1;border-radius:4px;box-sizing:border-box;font-size:15px;}
button{width:100%;padding:12px;margin-top:16px;background:#2563eb;color:#fff;border:none;border-radius:4px;font-size:16px;font-weight:bold;cursor:pointer;}
button:disabled{background:#94a3b8;}
.res{margin-top:20px;padding:12px;background:#f1f5f9;border-radius:4px;white-space:pre-wrap;font-family:monospace;font-size:13px;line-height:1.6;border:1px solid #cbd5e1;}
.err{margin-top:16px;padding:10px;background:#fee2e2;color:#dc2626;border-radius:4px;font-size:13px;}
</style>
</head>
<body>
<div class="box">
<h1>営業候補評価アプリ</h1>
<form method="POST">
<label>1. 受注側会社名（自社等）</label>
<input type="text" name="company_a" value="{{a}}" required placeholder="例: 株式会社〇〇">
<label>2. 取引先会社名（検討先）</label>
<input type="text" name="company_b" value="{{b}}" required placeholder="例: 株式会社△△">
<button type="submit">営業可能性を評価する</button>
</form>
{% if err %}<div class="err">{{err}}</div>{% endif %}
{% if res %}<div class="res">{{res}}</div>{% endif %}
</div>
</body>
</html>"""

# プロンプト定義（日本語厳格強制・フォーマット完全遵守）
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

def build_html_response(template_str, **kwargs):
    rendered = render_template_string(template_str, **kwargs)
    return Response(rendered, status=200, mimetype='text/html; charset=utf-8')

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        return build_html_response(RAW_HTML, a='', b='', res=None, err=None)
    
    a = request.form.get('company_a', '').strip()
    b = request.form.get('company_b', '').strip()
    
    if not a or not b:
        return build_html_response(RAW_HTML, a=a, b=b, res=None, err="両方の会社名を入力してください。")
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt_text = PROMPT.format(a=a, b=b)
        res = model.generate_content(prompt_text)
        return build_html_response(RAW_HTML, a=a, b=b, res=res.text, err=None)
    except Exception as e:
        try:
            model = genai.GenerativeModel('gemini-1.0-pro')
            prompt_text = PROMPT.format(a=a, b=b)
            res = model.generate_content(prompt_text)
            return build_html_response(RAW_HTML, a=a, b=b, res=res.text, err=None)
        except Exception as ex:
            return build_html_response(RAW_HTML, a=a, b=b, res=None, err=f"AI応答エラー: {str(ex)}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
