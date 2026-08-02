import os
from flask import Flask, Response, render_template_string, request
import google.generativeai as genai

app = Flask(__name__)

# 安定版Gemini APIの初期化
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# Web画面のHTMLテンプレート
HTML_TEMPLATE = """

　
    
    
    法人間取引 営業候補評価アプリ
    
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 16px; }
        .container { max-width: 600px; margin: 0 auto; background: #ffffff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
        h1 { font-size: 1.25rem; font-weight: bold; color: #0f172a; margin-bottom: 4px; text-align: center; }
        p.sub { font-size: 0.85rem; color: #64748b; margin-bottom: 20px; text-align: center; }
        .form-group { margin-bottom: 16px; }
        label { display: block; font-size: 0.9rem; font-weight: 600; margin-bottom: 6px; }
        input[type="text"] { width: 100%; padding: 12px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 1rem; box-sizing: border-box; }
        button { width: 100%; background: #2563eb; color: white; border: none; padding: 14px; font-size: 1rem; font-weight: bold; border-radius: 8px; cursor: pointer; margin-top: 8px; }
        button:disabled { background: #94a3b8; }
        .loading { display: none; text-align: center; margin-top: 20px; font-weight: bold; color: #2563eb; }
        .result-box { margin-top: 20px; padding: 16px; background: #f1f5f9; border-radius: 8px; font-family: monospace; white-space: pre-wrap; word-break: break-all; font-size: 0.9rem; line-height: 1.6; border: 1px solid #cbd5e1; }
        .error { color: #dc2626; background: #fef2f2; padding: 12px; border-radius: 8px; margin-top: 16px; font-size: 0.9rem; }
    


    
        営業候補評価アプリ
        SES & AIドリブン開発の二軸自動評価システム
        
        
            
                1. 受注側会社名（自社等）
                
            
            
                2. 取引先会社名（検討先）
                
            
            営業可能性を評価する
        

        🔍 公開情報を調査・分析中...(約10〜20秒かかります)

        {% if error %}
            {{ error }}
        {% endif %}

        {% if result %}
            {{ result }}
        {% endif %}
    

    
        function showLoading() {
            document.getElementById('loading').style.display = 'block';
            document.getElementById('submit-btn').disabled = true;
            document.getElementById('submit-btn').innerText = '評価を実行中...';
        }
    

"""

# プロンプト定義
PROMPT_TEMPLATE = """
あなたは法人間取引の営業評価AIです。
以下の「受注側会社」と「取引先」について、公開情報を調査・分析し、指定の配点とフォーマットに従って営業適合度を評価してください。

■入力情報
受注側会社：{company_a}
取引先：{company_b}

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
{company_b}

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
戦略的メリット　　Object　　　：[点数] / 10
信用・支払面の安心度　　　　　　：[点数] / 10
公開情報の十分さ　　　　　　　　：[点数] / 5

合計：
[合計点] / 100

総合判定：
[総合判定文]
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        html = render_template_string(HTML_TEMPLATE, company_a='', company_b='', result=None, error=None)
        return Response(html, mimetype='text/html; charset=utf-8')
    
    company_a = request.form.get('company_a', '').strip()
    company_b = request.form.get('company_b', '').strip()

    if not company_a or not company_b:
        html = render_template_string(HTML_TEMPLATE, company_a=company_a, company_b=company_b, result=None, error="両方の会社名を入力してください。")
        return Response(html, mimetype='text/html; charset=utf-8')

    try:
        prompt = PROMPT_TEMPLATE.format(company_a=company_a, company_b=company_b)
        
        # 安定版モデル呼び出し
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        
        html = render_template_string(HTML_TEMPLATE, company_a=company_a, company_b=company_b, result=response.text, error=None)
        return Response(html, mimetype='text/html; charset=utf-8')
    except Exception as e:
        html = render_template_string(HTML_TEMPLATE, company_a=company_a, company_b=company_b, result=None, error=f"評価処理中にエラーが発生しました: {str(e)}")
        return Response(html, mimetype='text/html; charset=utf-8')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
