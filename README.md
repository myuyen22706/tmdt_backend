# Hướng dẫn Deploy Backend lên Railway

## 1. Cấu hình đã được chuẩn bị sẵn
- `Dockerfile` & `railway.json`: Khởi chạy ứng dụng qua Uvicorn gắn với biến `$PORT` của Railway và có Healthcheck tại `/`.
- `Procfile` & `runtime.txt`: Dự phòng cho Nixpacks/Railpack.
- Tự động khởi tạo Indexes khi khởi động. Không còn tự nạp dữ liệu mẫu: database Atlas đã có sẵn dữ liệu.
- Hỗ trợ CORS cho toàn bộ domain `*.vercel.app` mặc định qua `BACKEND_CORS_ORIGIN_REGEX` và danh sách `BACKEND_CORS_ORIGINS`.

## 2. Các bước Deploy trên Railway
1. Đăng nhập [Railway.app](https://railway.app/) -> **New Project** -> **Deploy from GitHub repo**.
2. Chọn repository Backend, trong phần **Settings -> Source**, chọn branch **`quang-manh`**.
3. Vào tab **Variables**, thêm các biến môi trường sau (hoặc dùng **Raw Editor** dán từ `.env.example`):
   ```env
   ENVIRONMENT=production
   DEBUG=False
   SECRET_KEY=thay-bang-chuoi-bi-mat-dai-it-nhat-32-ky-tu
   MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
   MONGODB_DB_NAME=vo_ecommerce_atlas
   FRONTEND_URL=https://<ten-project-cua-ban>.vercel.app
   BACKEND_CORS_ORIGINS=["http://localhost:3000","https://<ten-project-cua-ban>.vercel.app"]
   MOMO_MOCK=True
   ```
4. Vào **Settings -> Networking** -> bấm **Generate Domain** để lấy URL public của Backend (ví dụ: `https://tmdt-backend-production.up.railway.app`).
5. Copy URL này sang cấu hình biến môi trường `NEXT_PUBLIC_API_URL` bên Vercel (Frontend).
