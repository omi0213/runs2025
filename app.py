from flask import Flask, send_file, render_template_string, request, jsonify
import pandas as pd
import io
from reportlab.lib.pagesizes import A5, landscape
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
import sys

app = Flask(__name__)
app.json.ensure_ascii = False

# --- 設定 ---
CSVファイル名 = "runs2025.csv"
フォントファイル名 = 'ipaexg.ttf'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
記録ファイルパス = os.path.join(BASE_DIR, CSVファイル名)
フォントファイルパス = os.path.join(BASE_DIR, フォントファイル名)

# --- フォント登録 ---
def フォント登録():
    if os.path.exists(フォントファイルパス):
        try:
            pdfmetrics.registerFont(TTFont('IPAexGothic', フォントファイルパス))
            print(f"✅ フォントロード成功: {フォントファイルパス}")
            return True
        except Exception as e:
            print(f"❌ フォント読込エラー: {e}")
    else:
        print(f"⚠️ フォントファイルなし: {フォントファイルパス}")
    return False

フォントOK = フォント登録()

# --- CSV読み込み（修正：列の順序対応） ---
def データ読み込み():
    if not os.path.exists(記録ファイルパス):
        return pd.DataFrame(columns=['名前', '種目', '記録'])

    try:
        df = pd.read_csv(記録ファイルパス, encoding='utf-8', header=None)
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(記録ファイルパス, encoding='cp932', header=None)
        except Exception:
            return pd.DataFrame(columns=['名前', '種目', '記録'])

    try:
        if df.shape[1] < 3:
            return pd.DataFrame(columns=['名前', '種目', '記録'])
            
        df = df.iloc[:, :3]
        
        # 【修正箇所】CSVの2列目が「記録」、3列目が「種目」であると仮定して読み込む設定に変更
        # もしこれで逆に「種目欄に記録が出る」のが直れば正解です。
        # 万が一また逆になった場合はここを ['名前', '種目', '記録'] に戻してください。
        df.columns = ['名前', '記録', '種目'] 
        
        # 前後の空白を削除
        df['名前'] = df['名前'].astype(str).str.strip()
        df['種目'] = df['種目'].astype(str).str.strip()
        df['記録'] = df['記録'].astype(str).str.strip()
        return df
    except Exception:
        return pd.DataFrame(columns=['名前', '種目', '記録'])

# --- HTML (記録欄を追加) ---
HTML = '''
<!DOCTYPE html>
<html lang="ja">
<head>
    <title>RUNS2025 記録証発行システム</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body{background:#f4f7f6;padding:20px;font-family:'Helvetica Neue', Arial, sans-serif;color:#333;}
        .container{max-width:600px;margin:40px auto;background:white;padding:30px;border-radius:8px;box-shadow:0 4px 15px rgba(0,0,0,0.1);}
        h1{text-align:center;color:#2c3e50; margin-bottom: 30px;}
        .form-group{margin-bottom:20px;}
        label{display:block;margin-bottom:8px;font-weight:bold;color:#555;}
        .search-box { display: flex; gap: 10px; }
        
        input{width:100%; padding:12px;border:1px solid #ddd;border-radius:4px;box-sizing:border-box;font-size:16px;}
        input[readonly] { background-color: #eee; color: #555; cursor: not-allowed; }
        
        .row { display: flex; gap: 20px; }
        .col { flex: 1; }

        .btn-search { background: #9b59b6; color: white; border: none; border-radius: 4px; padding: 0 20px; cursor: pointer; white-space: nowrap; }
        .btn-search:hover { background: #8e44ad; }
        .btn-group{display:flex;gap:10px;margin-top:30px;}
        button{padding:12px;border:none;border-radius:4px;font-size:16px;cursor:pointer;transition:background 0.3s;}
        .btn-preview{background:#3498db;color:white; flex:1;}
        .btn-preview:hover{background:#2980b9;}
        .btn-download{background:#27ae60;color:white; flex:1;}
        .btn-download:hover{background:#219a52;}
        .btn-close{background:#95a5a6;color:white; flex:1;}
        .preview-container{display:none;background:#fff;padding:20px;margin:30px 0;border:2px solid #f1c40f;border-radius:8px;}
        #result{margin-top:15px;text-align:center;font-weight:bold;color:#e74c3c;min-height: 20px;}
        #candidate-list { margin-top: 10px; display: none; border: 1px solid #ddd; border-radius: 4px; max-height: 200px; overflow-y: auto; background: #fafafa; }
        .candidate-item { padding: 10px; border-bottom: 1px solid #eee; cursor: pointer; transition: background 0.2s; display: flex; justify-content: space-between; }
        .candidate-item:last-child { border-bottom: none; }
        .candidate-item:hover { background: #e8f6ff; }
    </style>
</head>
<body>
<div class="container">
    <h1>RUNS2025 記録証ダウンロード</h1>
    
    <div class="form-group">
        <label for="search">お名前（一部でも検索できます）</label>
        <div class="search-box">
            <input type="text" id="search" placeholder="例：横山" value="">
            <button class="btn-search" onclick="searchCandidates()">候補を検索</button>
        </div>
        <div id="candidate-list"></div>
    </div>

    <div class="row">
        <div class="col">
            <div class="form-group">
                <label for="event">参加種目</label>
                <input type="text" id="event" placeholder="自動入力" readonly>
            </div>
        </div>
        <div class="col">
            <div class="form-group">
                <label for="record_display">記録</label>
                <input type="text" id="record_display" placeholder="自動入力" readonly>
            </div>
        </div>
    </div>

    <div class="btn-group">
        <button class="btn-preview" onclick="previewPDF()">内容をプレビュー確認</button>
    </div>
    
    <div id="result"></div>
    
    <div id="preview-container" class="preview-container">
        <h3 style="text-align:center;">記録証プレビュー</h3>
        <div id="preview-html"></div>
        <div class="btn-group">
            <button class="btn-download" onclick="downloadPDF()">PDFをダウンロード</button>
            <button class="btn-close" onclick="closePreview()">閉じる</button>
        </div>
    </div>
</div>
<script>
let previewData = null;

async function fetchData(url) {
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`サーバーエラー: ${response.status} ${response.statusText}`);
        }
        return await response.json();
    } catch (e) {
        throw e;
    }
}

function searchCandidates() {
    const query = document.getElementById('search').value.trim();
    const listDiv = document.getElementById('candidate-list');
    const resultDiv = document.getElementById('result');
    
    if(!query){
        resultDiv.innerHTML = '検索したい名前の一部を入力してください。';
        return;
    }
    resultDiv.innerHTML = '検索中...';
    listDiv.style.display = 'none';
    
    fetchData(`/api/search?q=${encodeURIComponent(query)}`)
    .then(data => {
        resultDiv.innerHTML = '';
        listDiv.innerHTML = '';
        if(data.length === 0) {
            resultDiv.innerHTML = '該当する名前が見つかりません。';
            return;
        }
        data.forEach(item => {
            const div = document.createElement('div');
            div.className = 'candidate-item';
            div.innerHTML = `<span>${item.名前}</span> <span style="color:#666;font-size:0.9em;">${item.種目} / ${item.記録}</span>`;
            // 選択時に record も渡すように変更
            div.onclick = () => selectCandidate(item.名前, item.種目, item.記録);
            listDiv.appendChild(div);
        });
        listDiv.style.display = 'block';
        resultDiv.innerHTML = `${data.length} 件見つかりました。リストから選択してください。`;
    })
    .catch(e => {
        console.error(e);
        resultDiv.innerHTML = 'エラー: ' + e.message;
    });
}

function selectCandidate(name, eventVal, recordVal) {
    document.getElementById('search').value = name;
    document.getElementById('event').value = eventVal;
    document.getElementById('record_display').value = recordVal; // 記録も表示
    
    document.getElementById('candidate-list').style.display = 'none';
    document.getElementById('result').innerHTML = '';
    previewPDF();
}

function previewPDF() {
    const name = document.getElementById('search').value.trim();
    const event = document.getElementById('event').value.trim();
    
    if(!name || !event){
        document.getElementById('result').innerHTML = '名前を検索して、候補リストから選択してください。';
        return;
    }
    document.getElementById('result').innerHTML = 'データ照会中...';
    
    const url = `/api/preview?name=${encodeURIComponent(name)}&event=${encodeURIComponent(event)}`;

    fetchData(url)
    .then(data => {
        document.getElementById('result').innerHTML = '';
        if(data.error) {
            document.getElementById('result').innerHTML = '⚠️ ' + data.error;
            document.getElementById('preview-container').style.display = 'none';
            return;
        }
        previewData = data;
        document.getElementById('preview-html').innerHTML = data.html;
        document.getElementById('preview-container').style.display = 'block';
    }).catch(e => {
        console.error(e);
        document.getElementById('result').innerHTML = 'エラー: ' + e.message;
    });
}

function downloadPDF() {
    if(previewData && previewData.url) {
        window.location.href = previewData.url;
    }
}
function closePreview() { 
    document.getElementById('preview-container').style.display = 'none'; 
    document.getElementById('result').innerHTML = '';
}
</script>
</body></html>
'''

# --- API ---

@app.route('/')
def ホーム():
    return render_template_string(HTML)

@app.route('/api/search')
def 候補検索():
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    df = データ読み込み()
    if df.empty:
        return jsonify([])
    try:
        mask = df['名前'].str.contains(query, na=False, regex=False)
        results = df[mask]
        return jsonify(results.to_dict('records'))
    except Exception:
        return jsonify([])

@app.route('/api/preview')
def プレビューAPI():
    name = request.args.get('name', '')
    event = request.args.get('event', '')
    
    df = データ読み込み()
    該当 = df[(df['名前'] == name) & (df['種目'] == event)]
    
    if 該当.empty:
        return jsonify({'error': f'該当データなし（名前: {name}, 種目: {event}）'})
    
    記録 = 該当.iloc[0]['記録']
    
    preview_html = f'''
    <div style="padding:20px;background:white;width:90%;margin:auto;border:1px solid #ccc; font-family: sans-serif; position: relative; overflow: hidden;">
        <div style="position:absolute; bottom:-50px; right:-50px; width:300px; height:200px; background:linear-gradient(135deg, transparent 40%, #d4af37 40%, #d4af37 60%, #a0a0a0 60%); opacity:0.3; transform: rotate(-20deg); border-radius: 50%;"></div>
        <div style="text-align:center;font-size:28px;font-weight:bold;color:#000;">RUNS<span style="color:#d4af37;">2025</span></div>
        <div style="text-align:center;font-size:16px;margin-top:5px;">FINISHER'S CERTIFICATE</div>
        <div style="text-align:center;font-size:12px;">記録証</div>
        <div style="margin-top:50px; padding-left: 20%;">
            <div style="font-size:14px;">氏名： <span style="font-size:20px; font-weight:bold;">{name}</span></div>
            <div style="font-size:14px; margin-top:15px;">種目： <span style="font-size:18px;">{event}</span></div>
        </div>
        <div style="text-align:center;font-size:40px;font-weight:bold;margin:40px 0; letter-spacing: 5px;">{記録}</div>
        <div style="text-align:center;font-size:14px;">2025.12.27</div>
        <div style="text-align:center;font-size:14px;font-style:italic;font-family:'Times New Roman', serif;margin-top:20px;line-height:1.5;">
            NICE RUNS!!<br>SHONAN RUNS
        </div>
    </div>
    '''
    from urllib.parse import quote
    download_url = f"/api/pdf?name={quote(name)}&event={quote(event)}"
    return jsonify({'html': preview_html, 'url': download_url})

@app.route('/api/pdf')
def PDF発行API():
    name = request.args.get('name', '')
    event = request.args.get('event', '')
    
    df = データ読み込み()
    該当 = df[(df['名前'] == name) & (df['種目'] == event)]
    if 該当.empty:
        return render_template_string('<h1>エラー：該当する記録が見つかりません。</h1>')
    
    記録 = 該当.iloc[0]['記録']
    buffer = io.BytesIO()
    
    c = canvas.Canvas(buffer, pagesize=landscape(A5))
    width, height = landscape(A5)
    
    jp_font = "IPAexGothic" if フォントOK else "Helvetica"
    bold_font = "Helvetica-Bold"
    signature_font = "Times-Italic" 
    gold_color = (0.85, 0.7, 0.2)
    gray_color = (0.6, 0.6, 0.6)
    black_color = (0, 0, 0)

    # 背景
    c.saveState()
    p_gray = c.beginPath()
    p_gray.moveTo(width, 0)
    p_gray.lineTo(width, height * 0.5)
    p_gray.curveTo(width * 0.7, height * 0.4, width * 0.8, height * 0.1, width * 0.5, 0)
    p_gray.close()
    c.setFillColorRGB(*gray_color)
    c.setStrokeColorRGB(*gray_color)
    c.drawPath(p_gray, fill=1, stroke=0)

    p_gold = c.beginPath()
    p_gold.moveTo(width, 0)
    p_gold.lineTo(width, height * 0.2)
    p_gold.curveTo(width * 0.8, height * 0.15, width * 0.7, height * 0.05, width * 0.6, 0)
    p_gold.close()
    c.setFillColorRGB(*gold_color)
    c.setStrokeColorRGB(*gold_color)
    c.drawPath(p_gold, fill=1, stroke=0)
    c.restoreState()
    
    # テキスト
    title_y = height - 70
    base_y = height / 2 + 30 
    time_y = base_y - 130

    c.setFillColorRGB(*black_color)
    c.setFont(bold_font, 40)
    runs_text = "RUNS"
    runs_width = c.stringWidth(runs_text, bold_font, 40)
    c.setFont(bold_font, 40)
    year_text = "2025"
    year_width = c.stringWidth(year_text, bold_font, 40)
    start_x = (width - (runs_width + year_width)) / 2
    c.drawString(start_x, title_y, runs_text)
    c.setFillColorRGB(*gold_color)
    c.drawString(start_x + runs_width, title_y, year_text)
    
    c.setFillColorRGB(*black_color)
    c.setFont(bold_font, 16)
    c.drawCentredString(width/2, title_y - 30, "FINISHER'S CERTIFICATE")
    c.setFont(jp_font, 12)
    c.drawCentredString(width/2, title_y - 50, "記録証")
    
    c.setFont(jp_font, 16)
    c.drawString(width * 0.25, base_y, "氏名：")
    c.setFont(jp_font, 22)
    c.drawString(width * 0.35, base_y, f"{name}")
    c.setFont(jp_font, 16)
    c.drawString(width * 0.25, base_y - 40, "種目：")
    c.setFont(jp_font, 18)
    c.drawString(width * 0.35, base_y - 40, f"{event}")
    
    c.setFont(bold_font, 50)
    c.drawCentredString(width/2, time_y, 記録)
    
    c.setFont(bold_font, 14)
    c.drawCentredString(width/2, 60, "2025.12.27")
    
    # フッター
    c.setFont(signature_font, 15)
    c.drawCentredString(width/2, 35, "NICE RUNS!!")
    c.drawCentredString(width/2, 18, "SHONAN RUNS")

    if not フォントOK:
        c.setFillColorRGB(1,0,0)
        c.setFont("Helvetica", 10)
        c.drawCentredString(width/2, height-10, "WARNING: Japanese font not found.")
    
    c.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="certificate.pdf")

if __name__ == '__main__':
    print("システム起動: http://localhost:5001 にアクセスしてください。")
    app.run(debug=True, host='0.0.0.0', port=5001)
