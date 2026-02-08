import os
import time
import random
import re
import json
import string
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import asyncio
import requests

# Bot ayarları - Environment variable'dan al
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8534710505:AAFxWGp00SD2PtBRd4Qj0h9U0nM8ESyeX5Y")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8522767291"))

# PORT ayarı Railway için
PORT = int(os.environ.get("PORT", 5000))

# Veri depolama dosyaları
DATA_FILE = "users_data.json"
BANNED_FILE = "banned_users.json"
VIP_KEYS_FILE = "vip_keys.json"
USER_MAILS_FILE = "user_mails.json"

# Kullanım limitleri
FREE_MAIL_LIMIT = 2      # Free kullanıcılar 2 mail
VIP_MAIL_LIMIT = 10      # VIP kullanıcılar 10 mail

# Başlangıçta verileri yükle
users_data = {}
banned_users = {}
vip_keys = {}
user_mails = {}

def load_data():
    global users_data, banned_users, vip_keys, user_mails
    
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                users_data = json.load(f)
        else:
            users_data = {}
    except Exception as e:
        print(f"Kullanıcı verileri yüklenirken hata: {e}")
        users_data = {}
    
    try:
        if os.path.exists(BANNED_FILE):
            with open(BANNED_FILE, 'r', encoding='utf-8') as f:
                banned_users = json.load(f)
        else:
            banned_users = {}
    except Exception as e:
        print(f"Banlı kullanıcılar yüklenirken hata: {e}")
        banned_users = {}
    
    try:
        if os.path.exists(VIP_KEYS_FILE):
            with open(VIP_KEYS_FILE, 'r', encoding='utf-8') as f:
                vip_keys = json.load(f)
        else:
            vip_keys = {}
    except Exception as e:
        print(f"VIP key'ler yüklenirken hata: {e}")
        vip_keys = {}
    
    try:
        if os.path.exists(USER_MAILS_FILE):
            with open(USER_MAILS_FILE, 'r', encoding='utf-8') as f:
                user_mails = json.load(f)
        else:
            user_mails = {}
    except Exception as e:
        print(f"Kullanıcı mailleri yüklenirken hata: {e}")
        user_mails = {}

def save_data():
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(users_data, f, ensure_ascii=False, indent=2)
        with open(BANNED_FILE, 'w', encoding='utf-8') as f:
            json.dump(banned_users, f, ensure_ascii=False, indent=2)
        with open(VIP_KEYS_FILE, 'w', encoding='utf-8') as f:
            json.dump(vip_keys, f, ensure_ascii=False, indent=2)
        with open(USER_MAILS_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_mails, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Veri kaydedilirken hata: {e}")

load_data()

# Mail API fonksiyonları - Basitleştirilmiş versiyon
def get_user_agent():
    """Basit user agent oluştur"""
    agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
    ]
    return random.choice(agents)

def headers():
    return {
        'User-Agent': get_user_agent(),
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }

def get_domains():
    try:
        r = requests.get('https://api.mail.tm/domains', headers=headers(), timeout=10)
        data = r.json()
        domains = data.get('hydra:member', [])
        active = [d['domain'] for d in domains if d.get('isActive')]
        return active if active else ['mail.tm']
    except:
        return ['mail.tm', 'example.com']

def create_mail_for_user(user_id, username, mail_index):
    domains = get_domains()
    
    # Basit bir email oluştur
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    email_username = f"user{user_id}_{random_suffix}"
    email = f"{email_username}@{domains[0]}"
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    
    try:
        # Mail.tm API'sine kayıt ol
        r = requests.post('https://api.mail.tm/accounts', 
                         json={"address": email, "password": password},
                         headers=headers(), timeout=15)
        
        if r.status_code in [200, 201]:
            # Token al
            t = requests.post('https://api.mail.tm/token', 
                             json={"address": email, "password": password},
                             headers=headers(), timeout=15)
            
            if t.status_code == 200:
                token_data = t.json()
                token = token_data.get('token')
                
                # Kullanıcının mail listesine ekle
                if str(user_id) not in user_mails:
                    user_mails[str(user_id)] = {}
                
                mail_id = f"mail_{mail_index}"
                user_mails[str(user_id)][mail_id] = {
                    'email': email,
                    'token': token,
                    'created_at': datetime.now().isoformat(),
                    'domain': domains[0],
                    'mail_count': 0,
                    'last_checked': None,
                    'messages': []
                }
                
                save_data()
                return email, token, mail_id
    except Exception as e:
        print(f"Mail oluşturma hatası: {e}")
    
    return None, None, None

def extract_code(text):
    if not text: 
        return None
    
    # 4-6 haneli sayıları bul
    codes = re.findall(r'\b\d{4,6}\b', text)
    if codes:
        return codes[0]
    
    return None

def check_single_mail(user_id, mail_id):
    if str(user_id) not in user_mails or mail_id not in user_mails[str(user_id)]:
        return []
    
    mail_data = user_mails[str(user_id)][mail_id]
    token = mail_data.get('token')
    
    if not token:
        return []
    
    try:
        h = headers()
        h['Authorization'] = f'Bearer {token}'
        r = requests.get('https://api.mail.tm/messages?page=1', headers=h, timeout=15)
        
        if r.status_code != 200:
            return []
        
        data = r.json()
        messages = data.get('hydra:member', []) if isinstance(data, dict) else []
        
        new_mails = []
        for msg in messages[:5]:  # Sadece ilk 5 mesajı kontrol et
            msg_id = str(msg.get('id', ''))
            
            # Daha önce bu mesajı kaydettik mi?
            existing_msg_ids = [m.get('msg_id', '') for m in mail_data['messages']]
            if msg_id in existing_msg_ids:
                continue
            
            # Mesaj detaylarını al
            try:
                detail = requests.get(f"https://api.mail.tm/messages/{msg_id}", 
                                    headers=h, timeout=15).json()
                
                sender = detail.get('from', {}).get('address', 'Bilinmiyor')
                subject = detail.get('subject', 'Konu yok')
                text = detail.get('text') or detail.get('html') or ''
                
                if isinstance(text, list):
                    text = ' '.join(text)
                
                # HTML temizleme
                text = re.sub('<[^<]+?>', ' ', text)
                
                code = extract_code(text)
                
                mail_info = {
                    'msg_id': msg_id,
                    'sender': sender,
                    'subject': subject,
                    'text': text[:300],
                    'code': code,
                    'received_at': datetime.now().isoformat()
                }
                
                # Mesajı kaydet
                user_mails[str(user_id)][mail_id]['messages'].append(mail_info)
                user_mails[str(user_id)][mail_id]['mail_count'] += 1
                user_mails[str(user_id)][mail_id]['last_checked'] = datetime.now().isoformat()
                
                new_mails.append(mail_info)
                
            except Exception as e:
                print(f"Mesaj detay hatası: {e}")
                continue
        
        save_data()
        return new_mails
        
    except Exception as e:
        print(f"Mail kontrol hatası: {e}")
        return []

def get_user_mail_count(user_id):
    if str(user_id) not in user_mails:
        return 0
    return len(user_mails[str(user_id)])

def can_create_mail(user_id):
    user_id_str = str(user_id)
    
    if user_id_str not in users_data:
        return True, FREE_MAIL_LIMIT, 0
    
    user_data = users_data[user_id_str]
    current_count = get_user_mail_count(user_id)
    
    if user_data.get('is_vip', False):
        return current_count < VIP_MAIL_LIMIT, VIP_MAIL_LIMIT, current_count
    else:
        return current_count < FREE_MAIL_LIMIT, FREE_MAIL_LIMIT, current_count

# VIP Key sistemi
def generate_vip_key(days, max_uses):
    key = f"vip-{''.join(random.choices(string.ascii_letters + string.digits, k=12))}"
    
    vip_keys[key] = {
        'days': days,
        'max_uses': max_uses,
        'used_count': 0,
        'created_at': datetime.now().isoformat(),
        'expires_at': (datetime.now() + timedelta(days=days)).isoformat(),
        'used_by': []
    }
    
    save_data()
    return key

def use_vip_key(user_id, key):
    user_id_str = str(user_id)
    
    if key not in vip_keys:
        return False, "❌ Geçersiz key!"
    
    key_data = vip_keys[key]
    
    # Kullanım limiti kontrolü
    if key_data['used_count'] >= key_data['max_uses']:
        return False, "❌ Bu key'in kullanım limiti dolmuş!"
    
    # Süre kontrolü
    expires_at = datetime.fromisoformat(key_data['expires_at'])
    if datetime.now() > expires_at:
        return False, "❌ Bu key'in süresi dolmuş!"
    
    # Kullanıcı daha önce bu key'i kullanmış mı?
    if user_id_str in key_data['used_by']:
        return False, "❌ Bu key'i zaten kullanmışsınız!"
    
    # VIP yap
    if user_id_str not in users_data:
        users_data[user_id_str] = {}
    
    users_data[user_id_str]['is_vip'] = True
    users_data[user_id_str]['vip_until'] = expires_at.isoformat()
    users_data[user_id_str]['vip_key'] = key
    users_data[user_id_str]['vip_since'] = datetime.now().isoformat()
    
    # Key istatistiklerini güncelle
    key_data['used_count'] += 1
    key_data['used_by'].append(user_id_str)
    
    save_data()
    return True, f"✅ VIP oldunuz! VIP süresi: {expires_at.strftime('%d/%m/%Y %H:%M')}"

# Ana menü fonksiyonu
async def show_main_menu(user_id, username, query=None, message=None):
    user_id_str = str(user_id)
    
    # Kullanıcıyı kaydet (eğer yoksa)
    if user_id_str not in users_data:
        users_data[user_id_str] = {
            'username': username,
            'joined_at': datetime.now().isoformat(),
            'is_vip': False,
            'mail_count': 0,
            'last_active': datetime.now().isoformat()
        }
        save_data()
    
    # Aktif mail sayısını al
    mail_count = get_user_mail_count(user_id)
    is_vip = users_data[user_id_str].get('is_vip', False)
    limit = VIP_MAIL_LIMIT if is_vip else FREE_MAIL_LIMIT
    
    keyboard = [
        [InlineKeyboardButton("📧 Yeni Mail Oluştur", callback_data='create_mail')],
        [InlineKeyboardButton("📨 Maillerim", callback_data='my_mails')],
        [InlineKeyboardButton("🔑 VIP Key Kullan", callback_data='use_vip_key')],
        [InlineKeyboardButton("ℹ️ Yardım", callback_data='help'),
         InlineKeyboardButton("📊 Durum", callback_data='status')]
    ]
    
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("⚡ Admin Panel", callback_data='admin_panel')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    status_text = "VIP 🎖️" if is_vip else "Ücretsiz 👤"
    limit_text = f"10 mail (VIP)" if is_vip else f"2 mail (Ücretsiz)"
    
    welcome_text = f"""
🚀 *Mail Bot'a Hoş Geldin* @{username}!

📊 *Durumunuz:* {status_text}
📧 *Mail Sayısı:* {mail_count}/{limit}
🎯 *Limit:* {limit_text}

Bir işlem seçmek için butonlara tıklayın!
    """
    
    if query:
        await query.edit_message_text(welcome_text, 
                                     reply_markup=reply_markup,
                                     parse_mode='Markdown')
    elif message:
        await message.reply_text(welcome_text,
                               reply_markup=reply_markup,
                               parse_mode='Markdown')

# Telegram Bot Komutları
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or str(user_id)
    
    if str(user_id) in banned_users:
        await update.message.reply_text("❌ Hesabınız banlanmıştır!")
        return
    
    await show_main_menu(user_id, username, message=update.message)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    username = query.from_user.username or str(user_id)
    
    if str(user_id) in banned_users:
        await query.edit_message_text("❌ Hesabınız banlanmıştır!")
        return
    
    if query.data == 'create_mail':
        can_create, limit, current = can_create_mail(user_id)
        
        if not can_create:
            status = "VIP 🎖️" if users_data[str(user_id)].get('is_vip', False) else "Ücretsiz 👤"
            
            await query.edit_message_text(
                f"❌ *Mail Limiti Doldu!*\n\n"
                f"📊 *Durumunuz:* {status}\n"
                f"📧 *Mevcut Mail:* {current}/{limit}\n\n"
                f"VIP olmak için 'VIP Key Kullan' butonuna tıklayın!",
                parse_mode='Markdown'
            )
            
            keyboard = [[InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text("Ana menüye dönmek için:", reply_markup=reply_markup)
            return
        
        # Yeni mail oluştur
        username_prefix = f"user{user_id}"
        mail_index = current + 1
        
        await query.edit_message_text("⏳ *Mail oluşturuluyor... Lütfen bekleyin!*", parse_mode='Markdown')
        
        email, token, mail_id = create_mail_for_user(user_id, username_prefix, mail_index)
        
        if email:
            keyboard = [
                [InlineKeyboardButton("📨 Maillerim", callback_data='my_mails')],
                [InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"✅ *Yeni Mail Oluşturuldu!*\n\n"
                f"📧 *Mail Adresin:* `{email}`\n"
                f"🔢 *Mail No:* {mail_index}\n"
                f"📊 *Toplam Mail:* {mail_index}/{limit}\n\n"
                f"Bu mailin gelen kutusunu 'Maillerim' bölümünden kontrol edebilirsin.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text("❌ Mail oluşturulamadı. Lütfen tekrar deneyin.")
            keyboard = [[InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text("Ana menüye dönmek için:", reply_markup=reply_markup)
    
    elif query.data == 'my_mails':
        if str(user_id) not in user_mails or not user_mails[str(user_id)]:
            await query.edit_message_text("📭 Henüz mail adresiniz yok. Önce mail oluşturun!")
            
            keyboard = [[InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text("Ana menüye dönmek için:", reply_markup=reply_markup)
            return
        
        mails = user_mails[str(user_id)]
        keyboard = []
        
        for mail_id, mail_data in mails.items():
            mail_num = mail_id.split('_')[1] if '_' in mail_id else "1"
            btn_text = f"📧 Mail {mail_num}: {mail_data['email'][:15]}..."
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f'view_mail_{mail_id}')])
        
        keyboard.append([InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"📨 *Mailleriniz* ({len(mails)} adet)\n\nKontrol etmek istediğiniz maili seçin:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif query.data.startswith('view_mail_'):
        mail_id = query.data.replace('view_mail_', '')
        
        if str(user_id) not in user_mails or mail_id not in user_mails[str(user_id)]:
            await query.edit_message_text("❌ Mail bulunamadı!")
            return
        
        mail_data = user_mails[str(user_id)][mail_id]
        email = mail_data['email']
        
        # Bu mail için gelen kutusunu kontrol et
        new_mails = check_single_mail(user_id, mail_id)
        
        total_messages = len(mail_data['messages'])
        
        response = f"""
📧 *Mail Detayları*

📧 *Adres:* `{email}`
📅 *Oluşturulma:* {mail_data['created_at'][:10]}
📬 *Toplam Mesaj:* {total_messages}
        """
        
        if new_mails:
            response += f"\n✅ *{len(new_mails)} yeni mail!*\n"
            for mail in new_mails[-2:]:
                response += f"\n• *Gönderen:* {mail['sender'][:20]}\n"
                if mail['code']:
                    response += f"  🔐 *KOD:* `{mail['code']}`\n"
                response += f"  *Konu:* {mail['subject'][:20]}..."
        elif total_messages > 0:
            response += f"\n📭 *Son Mailler:*\n"
            for mail in mail_data['messages'][-2:]:
                response += f"\n• *Gönderen:* {mail['sender'][:20]}\n"
                if mail.get('code'):
                    response += f"  🔐 *KOD:* `{mail['code']}`\n"
                response += f"  *Konu:* {mail['subject'][:20]}..."
        else:
            response += "\n\n📭 *Gelen kutusu boş*"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Maili Kontrol Et", callback_data=f'check_mail_{mail_id}')],
            [InlineKeyboardButton("📨 Tüm Maillerim", callback_data='my_mails'),
             InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(response, 
                                     reply_markup=reply_markup,
                                     parse_mode='Markdown')
    
    elif query.data == 'use_vip_key':
        await query.edit_message_text(
            "🔑 *VIP Key Kullan*\n\n"
            "VIP key'inizi gönderin:\n\n"
            "Örnek: `vip-xxxxxxxxxxxx`\n\n"
            "VIP olunca 10 mail oluşturabilirsiniz!",
            parse_mode='Markdown'
        )
        context.user_data['awaiting_vip_key'] = True
    
    elif query.data == 'help':
        help_text = """
🤖 *Mail Bot Yardım*

*Komutlar:*
/start - Botu başlat
/mails - Maillerimi listele
/vip - VIP bilgileri
/help - Yardım menüsü

*Mail Limitleri:*
• Ücretsiz kullanıcılar: 2 mail
• VIP kullanıcılar: 10 mail

*VIP Sistemi:*
VIP olmak için VIP key gerek.
Key kullanmak için "VIP Key Kullan" butonuna tıklayın.
        """
        
        keyboard = [[InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(help_text, 
                                     reply_markup=reply_markup,
                                     parse_mode='Markdown')
    
    elif query.data == 'status':
        can_create, limit, current = can_create_mail(user_id)
        is_vip = users_data.get(str(user_id), {}).get('is_vip', False)
        status = "VIP 🎖️" if is_vip else "Ücretsiz 👤"
        
        status_text = f"""
📊 *Hesap Durumunuz*

👤 *Durum:* {status}
📧 *Mail Sayısı:* {current}/{limit}
{'✅ Yeni mail oluşturabilirsiniz' if can_create else '❌ Mail limitiniz doldu'}
        """
        
        keyboard = [
            [InlineKeyboardButton("📧 Yeni Mail", callback_data='create_mail')],
            [InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(status_text, 
                                     reply_markup=reply_markup,
                                     parse_mode='Markdown')
    
    elif query.data == 'main_menu':
        await show_main_menu(user_id, username, query=query)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.message.text.strip()
    
    # VIP key kullanımı
    if context.user_data.get('awaiting_vip_key'):
        context.user_data['awaiting_vip_key'] = False
        
        success, result_msg = use_vip_key(user_id, message_text)
        
        if success:
            await update.message.reply_text(f"✅ {result_msg}")
            await show_main_menu(user_id, update.effective_user.username or str(user_id), message=update.message)
        else:
            await update.message.reply_text(f"{result_msg}\n\nTekrar denemek için /start yazın.")
        return
    
    # Normal mesajları işle
    await update.message.reply_text("Komutlar için /start yazın.")

# Komutlar
async def mails_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if str(user_id) not in user_mails or not user_mails[str(user_id)]:
        await update.message.reply_text("📭 Henüz mail adresiniz yok. Önce mail oluşturun!")
        return
    
    mails = user_mails[str(user_id)]
    keyboard = []
    
    for mail_id, mail_data in mails.items():
        mail_num = mail_id.split('_')[1] if '_' in mail_id else "1"
        btn_text = f"📧 Mail {mail_num}: {mail_data['email'][:15]}..."
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f'view_mail_{mail_id}')])
    
    keyboard.append([InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📨 *Mailleriniz* ({len(mails)} adet)\n\nKontrol etmek istediğiniz maili seçin:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Ana fonksiyon - Railway için düzenlenmiş
def main():
    print("🚀 Mail Bot başlatılıyor...")
    print(f"🤖 Admin ID: {ADMIN_ID}")
    print(f"📊 Kullanıcı sayısı: {len(users_data)}")
    print(f"📧 Toplam mail: {sum(len(mails) for mails in user_mails.values())}")
    print("═" * 50)
    
    # Bot'u başlat
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Komut handler'ları
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mails", mails_command))
    app.add_handler(CommandHandler("help", start))
    
    # Callback query handler'ları
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Mesaj handler'ı
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Bot çalışıyor...")
    print("📝 Kullanıcılar için: /start")
    print("═" * 50)
    
    # Railway için webhook veya polling
    if "RAILWAY_STATIC_URL" in os.environ:
        # Railway'de webhook kullan
        from telegram.ext import ApplicationBuilder
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        # Komutları ekle
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("mails", mails_command))
        app.add_handler(CallbackQueryHandler(button_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Webhook ayarla
        url = os.environ.get("RAILWAY_STATIC_URL", "")
        if url:
            print(f"🌐 Webhook URL: {url}")
            app.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path=BOT_TOKEN,
                webhook_url=f"{url}/{BOT_TOKEN}"
            )
        else:
            app.run_polling()
    else:
        # Local'de polling kullan
        app.run_polling()

if __name__ == "__main__":
    main()
