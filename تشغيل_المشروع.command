#!/bin/zsh

# الانتقال إلى مجلد المشروع الحالي بشكل صحيح
DIR="$( cd "$( dirname "$0" )" && pwd )"
cd "$DIR"

echo "=========================================="
echo "        تشغيل مشروع نظام المستشفى        "
echo "=========================================="
echo ""

# التحقق من البيئة الافتراضية وتفعيلها
if [ ! -d "venv" ] || [ ! -f "venv/bin/activate" ]; then
    echo "[!] البيئة الافتراضية غير مكتملة، جاري إنشاؤها وتثبيت المكتبات المطلوبة..."
    python3 -m venv venv
    source venv/bin/activate
    python3 -m pip install -r requirements.txt
else
    source venv/bin/activate
fi

echo "[✓] تم تفعيل البيئة الافتراضية بنجاح."
echo "[→] جاري فتح التوثيق والواجهة في المتصفح..."

# فتح المتصفح تلقائياً بعد ثانيتين
(sleep 2 && open "http://127.0.0.1:8000/docs") &

echo "[→] جاري تشغيل السيرفر (Uvicorn) على Port 8000..."
echo "------------------------------------------"
echo "ملاحظة: يمكنك إغلاق النافذة أو الضغط على Ctrl+C لإيقاف التشغيل."
echo ""

# تشغيل خادم FastAPI
python3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
