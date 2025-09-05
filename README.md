# Discord Bot Control Panel (Flask + Pycord)

เว็บแผงควบคุมบอท Discord สำหรับ VPS
- กรอก/แก้ไขโทเคนบอทได้จากหน้าเว็บ
- เพิ่ม/แก้ไข/ลบ "คำสั่งแบบพิมพ์ข้อความ" (เช่น พิมพ์ `สวัสดี` แล้วให้ตอบกลับ)
- จำกัดการใช้งานคำสั่งแต่ละรายการเฉพาะ "ห้อง (Channel IDs)" และ/หรือ "ผู้ใช้ (User IDs)"
- ปุ่ม `Start`, `Stop`, `Restart` ตัวบอท ได้จากหน้า Dashboard
- UI ใช้ง่าย (Bootstrap 5 จาก CDN)

> หมายเหตุ: ฟีเจอร์นี้ใช้ **Message Content Intent** ของ Discord – ต้องเปิด *MESSAGE CONTENT INTENT* ใน Developer Portal ของบอทของคุณด้วย

## โครงสร้างโปรเจกต์

```
discord_bot_panel/
├─ app.py               # เว็บแอป Flask + แผงควบคุม
├─ bot_runner.py        # ตัวบอท (รันเป็น subprocess)
├─ db.py                # ตัวช่วยจัดการฐานข้อมูล SQLite
├─ requirements.txt
├─ templates/
│  ├─ base.html
│  ├─ dashboard.html
│  ├─ login.html
│  ├─ settings.html
│  ├─ commands_list.html
│  └─ command_form.html
└─ static/
   └─ (สำรองไฟล์ static เพิ่มได้)
```

## วิธีติดตั้ง (บน VPS ที่มี Python 3.10+)

```bash
cd discord_bot_panel
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# เริ่มแบบโหมดพัฒนา
python app.py
# หรือรันด้วย Gunicorn (แนะนำสำหรับ production)
# gunicorn -w 2 -b 0.0.0.0:8000 app:app
```

แล้วเปิดเบราว์เซอร์ไปที่ `http://<IP หรือโดเมนของ VPS>:5000` (หรือพอร์ตที่คุณใช้)  
*รหัสผ่านแอดมิน* จะถูกตั้งค่าครั้งแรกในหน้า Login (จะบันทึก hashed password ใน DB)

## การใช้งาน

1. ล็อกอิน
2. ไปที่ Settings > ใส่โทเคนบอท > Save
3. ที่หน้า Dashboard กด `Start Bot`
4. ที่เมนู Commands สามารถสร้างคำสั่ง (Trigger/Response) ได้ และตั้งค่าจำกัดช่อง/ผู้ใช้ได้
   - Channel IDs: ใส่เป็นเลขไอดีช่อง (comma-separated) เช่น `1234567890,9876543210`
   - User IDs: ใส่เป็นเลขไอดีผู้ใช้ เช่น `111,222,333`

### ตัวอย่าง:
- Trigger: `สวัสดี`
- Response: `ดีจ้า! ยินดีที่ได้รู้จัก`
- Channel IDs: เว้นว่าง = ใช้ได้ทุกห้อง / ใส่ ID = จำกัดเฉพาะห้องนั้น
- User IDs: เว้นว่าง = ใช้ได้ทุกคน / ใส่ ID = จำกัดเฉพาะผู้ใช้ที่ระบุ

## systemd (ตัวอย่างไฟล์ service สำหรับแผงควบคุม)

สร้างไฟล์ `/etc/systemd/system/discord-panel.service` เช่น

```
[Unit]
Description=Discord Bot Control Panel
After=network.target

[Service]
WorkingDirectory=/path/to/discord_bot_panel
ExecStart=/path/to/discord_bot_panel/.venv/bin/gunicorn -w 2 -b 0.0.0.0:8000 app:app
Restart=on-failure
User=www-data
Group=www-data
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable discord-panel
sudo systemctl start discord-panel
```

> ตัวบอทจะถูกสตาร์ท/หยุด/รีสตาร์ทผ่านหน้าเว็บ (subprocess) — ไม่ต้องสร้าง service แยกให้บอท

## ความปลอดภัย
- เก็บโทเคนไว้ใน DB (ฝั่งเซิร์ฟเวอร์) — จำกัดสิทธิ์ไฟล์/โฟลเดอร์ให้เหมาะสม
- ตั้งรหัสผ่าน Admin ที่คาดเดายาก
- ใช้ Reverse Proxy (เช่น Nginx) + HTTPS (Let’s Encrypt) ในการเปิดสู่สาธารณะ
- พิจารณาใส่ Basic Auth ชั้นนอก (ถ้าต้องการ)

## หมายเหตุการใช้งาน
- เมื่อเพิ่ม/แก้ไขคำสั่งในหน้าเว็บ บอทจะเห็นผลทันที (หน้าเว็บจะส่งสัญญาณให้บอท reload cache อัตโนมัติภายในไม่กี่วินาที)
- ถ้ากด Stop แล้ว Start ใหม่ จะเป็นการรีสตาร์ท subprocess ของบอท
