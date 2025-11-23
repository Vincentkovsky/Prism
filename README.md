# whitepaper_rag

激活venv环境
source backend/venv/bin/activate
安装依赖
pip install -r backend/requirements.txt
启动项目
python -m uvicorn backend.app.main:app --reload    

运行测试
pytest

## Supabase Auth 配置

1. 在项目根目录创建 `.env`，同时供前后端读取：
   ```bash
   VITE_SUPABASE_URL=your_supabase_project_url
   VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
   ```
2. 在 Supabase 控制台开启 Google Provider，并将回调地址配置为 `https://<project>.supabase.co/auth/v1/callback`（以及本地的 `http://localhost:5173`）。
3. 安装前端依赖并启动：
   ```bash
   cd frontend
   npm install
   npm run dev
   ```