import requests
import time
import random
import re
import os
import json
import threading
import string
from datetime import datetime, timedelta
from fake_useragent import UserAgent
import pyfiglet
from colorama import Fore, Style, init
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import asyncio

init(autoreset=True)

# Bot ayarları
BOT_TOKEN = "8534710505:AAFxWGp00SD2PtBRd4Qj0h9U0nM8ESyeX5Y"
ADMIN_ID = 8522767291

# Veri depolama
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
            with open(DATA_FILE, 'r') as f:
                users_data = json.load(f)
        else:
            users_data = {}
    except:
        users_data = {}
    
    try:
        if os.path.exists(BANNED_FILE):
            with open(BANNED_FILE, 'r') as f:
                banned_users = json.load(f)
        else:
            banned_users = {}
    except:
        banned_users = {}
    
    try:
        if os.path.exists(VIP_KEYS_FILE):
            with open(VIP_KEYS_FILE, 'r') as f:
                vip_keys = json.load(f)
        else:
            vip_keys = {}
    except:
        vip_keys = {}
    
    try:
        if os.path.exists(USER_MAILS_FILE):
            with open(USER_MAILS_FILE, 'r') as f:
                user_mails = json.load(f)
        else:
            user_mails = {}
    except:
        user_mails = {}

def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump(users_data, f)
    with open(BANNED_FILE, 'w') as f:
        json.dump(banned_users, f)
    with open(VIP_KEYS_FILE, 'w') as f:
        json.dump(vip_keys, f)
    with open(USER_MAILS_FILE, 'w') as f:
        json.dump(user_mails, f)

load_data()

# Mail API fonksiyonları
ua = UserAgent()

def headers():
    return {
        'User-Agent': ua.random,
        'Accept': 'application/ld+json',
        'Content-Type': 'application/json',
        'Origin': 'https://mail.tm',
        'Referer': 'https://mail.tm/',
        'X-Coded-By': '@Scorpion292439'
    }

def get_domains():
    try:
        r = requests.get('https://api.mail.tm/domains', headers=headers(), timeout=15)
        data = r.json()
        domains = data.get('hydra:member', [])
        active = [d['domain'] for d in domains if d.get('isActive')]
        return active
    except:
        return ['comfythings.com', 'tempmail1.com', 'disposablemail.com']

def create_mail_for_user(user_id, username, mail_index):
    domains = get_domains()
    random.shuffle(domains)
    
    for domain in domains:
        # Random username oluştur
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        email_username = f"{username}{random_suffix}{mail_index}"
        email = f"{email_username}@{domain}"
        pwd = "Temp" + ''.join(random.choices("0123456789", k=10))
        
        try:
            r = requests.post('https://api.mail.tm/accounts', 
                            json={"address": email, "password": pwd},
                            headers=headers(), timeout=15)
            
            if r.status_code == 201:
                t = requests.post('https://api.mail.tm/token', 
                                json={"address": email, "password": pwd},
                                headers=headers(), timeout=15)
                token = t.json().get('token')
                
                # Kullanıcının mail listesine ekle
                if str(user_id) not in user_mails:
                    user_mails[str(user_id)] = {}
                
                mail_id = f"mail_{mail_index}"
                user_mails[str(user_id)][mail_id] = {
                    'email': email,
                    'token': token,
                    'created_at': str(datetime.now()),
                    'domain': domain,
                    'mail_count': 0,
                    'last_checked': None,
                    'messages': []
                }
                
                save_data()
                
                return email, token, mail_id
        except Exception as e:
            print(f"Hata: {e}")
            continue
    
    return None, None, None

def extract_code(text):
    if not text: 
        return None
    # 4-10 haneli sayıları bul
    codes = re.findall(r'\b\d{4,10}\b', text)
    if codes:
        return max(codes, key=len)
    
    # Eğer sayı bulunamazsa, 6 haneli OTP formatını ara
    otp_patterns = [
        r'OTP[:\s]*(\d{6})',
        r'kod[:\s]*(\d{6})',
        r'code[:\s]*(\d{6})',
        r'doğrulama[:\s]*(\d{6})',
        r'verification[:\s]*(\d{6})'
    ]
    
    for pattern in otp_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None

def check_single_mail(user_id, mail_id):
    if str(user_id) not in user_mails:
        return []
    
    if mail_id not in user_mails[str(user_id)]:
        return []
    
    mail_data = user_mails[str(user_id)][mail_id]
    token = mail_data['token']
    
    try:
        h = headers()
        h['Authorization'] = f'Bearer {token}'
        r = requests.get('https://api.mail.tm/messages?page=1', headers=h, timeout=20)
        
        if r.status_code == 401:
            return []
        
        data = r.json()
        messages = data.get('hydra:member', []) if isinstance(data, dict) else data
        
        new_mails = []
        for msg in messages:
            # Mesaj ID'sini kontrol et (daha önce kaydedilmiş mi)
            msg_id = str(msg.get('id', ''))
            existing_msg_ids = [m.get('msg_id', '') for m in mail_data['messages']]
            
            if msg_id in existing_msg_ids:
                continue
            
            detail = requests.get(f"https://api.mail.tm/messages/{msg['id']}", 
                                headers=h, timeout=20).json()
            
            sender = detail.get('from', {}).get('address', 'Bilinmiyor')
            subject = detail.get('subject', 'Konu yok')
            text = detail.get('text') or detail.get('html') or ''
            
            if isinstance(text, list):
                text = ' '.join([t for t in text if isinstance(t, str)])
            text = re.sub('<[^<]+?>', ' ', text)
            
            code = extract_code(text)
            
            mail_info = {
                'msg_id': msg_id,
                'sender': sender,
                'subject': subject,
                'text': text[:500],
                'code': code,
                'received_at': str(datetime.now())
            }
            
            # Mesajı kaydet
            user_mails[str(user_id)][mail_id]['messages'].append(mail_info)
            user_mails[str(user_id)][mail_id]['mail_count'] += 1
            user_mails[str(user_id)][mail_id]['last_checked'] = str(datetime.now())
            
            new_mails.append(mail_info)
        
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
    if str(user_id) not in users_data:
        return True, FREE_MAIL_LIMIT, 0  # Yeni kullanıcı
    
    user_data = users_data[str(user_id)]
    current_count = get_user_mail_count(user_id)
    
    if user_data.get('is_vip', False):
        return current_count < VIP_MAIL_LIMIT, VIP_MAIL_LIMIT, current_count
    else:
        return current_count < FREE_MAIL_LIMIT, FREE_MAIL_LIMIT, current_count

# VIP Key sistemi
def generate_vip_key(days, max_uses):
    key = f"vip-key-email-bot-{''.join(random.choices(string.ascii_letters + string.digits, k=15))}"
    
    vip_keys[key] = {
        'days': days,
        'max_uses': max_uses,
        'used_count': 0,
        'created_at': str(datetime.now()),
        'expires_at': str(datetime.now() + timedelta(days=days)),
        'used_by': []
    }
    
    save_data()
    return key

def use_vip_key(user_id, key):
    if key not in vip_keys:
        return False, "❌ Geçersiz key!"
    
    key_data = vip_keys[key]
    
    # Kullanım limiti kontrolü
    if key_data['used_count'] >= key_data['max_uses']:
        return False, "❌ Bu key'in kullanım limiti dolmuş!"
    
    # Süre kontrolü
    expires_at = datetime.fromisoformat(key_data['expires_at'].replace('Z', '+00:00'))
    if datetime.now() > expires_at:
        return False, "❌ Bu key'in süresi dolmuş!"
    
    # Kullanıcı daha önce bu key'i kullanmış mı?
    if str(user_id) in key_data['used_by']:
        return False, "❌ Bu key'i zaten kullanmışsınız!"
    
    # VIP yap
    if str(user_id) not in users_data:
        users_data[str(user_id)] = {}
    
    users_data[str(user_id)]['is_vip'] = True
    users_data[str(user_id)]['vip_until'] = str(expires_at)
    users_data[str(user_id)]['vip_key'] = key
    users_data[str(user_id)]['vip_since'] = str(datetime.now())
    
    # Key istatistiklerini güncelle
    key_data['used_count'] += 1
    key_data['used_by'].append(str(user_id))
    
    save_data()
    return True, f"✅ VIP oldunuz! VIP süresi: {expires_at.strftime('%d/%m/%Y %H:%M')}\n\n🎉 Artık 10 mail oluşturabilirsiniz!"

# Ana menü fonksiyonu
async def show_main_menu(user_id, username, query=None, message=None):
    """Ana menüyü gösteren ortak fonksiyon"""
    
    # Kullanıcıyı kaydet (eğer yoksa)
    if str(user_id) not in users_data:
        users_data[str(user_id)] = {
            'username': username,
            'joined_at': str(datetime.now()),
            'is_vip': False,
            'mail_count': 0,
            'last_active': str(datetime.now())
        }
        save_data()
    
    # Aktif mail sayısını al
    mail_count = get_user_mail_count(user_id)
    is_vip = users_data[str(user_id)].get('is_vip', False)
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

📋 *Özellikler:*
• Her mail için ayrı gelen kutusu
• Doğrulama kodları otomatik yakalama
• VIP sistem (10 mail hakkı)

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
            limit_text = "10 mail" if users_data[str(user_id)].get('is_vip', False) else "2 mail"
            
            await query.edit_message_text(
                f"❌ *Mail Limiti Doldu!*\n\n"
                f"📊 *Durumunuz:* {status}\n"
                f"📧 *Mevcut Mail:* {current}/{limit}\n"
                f"🎯 *Limitiniz:* {limit_text}\n\n"
                f"VIP olmak için 'VIP Key Kullan' butonuna tıklayın!",
                parse_mode='Markdown'
            )
            
            # Ana menü butonu ekle
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
                [InlineKeyboardButton("📧 Yeni Mail Oluştur", callback_data='create_mail')],
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
    
    elif query.data == 'my_mails':
        if str(user_id) not in user_mails or not user_mails[str(user_id)]:
            await query.edit_message_text("📭 Henüz mail adresiniz yok. Önce mail oluşturun!")
            
            # Ana menü butonu ekle
            keyboard = [[InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text("Ana menüye dönmek için:", reply_markup=reply_markup)
            return
        
        mails = user_mails[str(user_id)]
        keyboard = []
        
        for mail_id, mail_data in mails.items():
            mail_num = mail_id.split('_')[1] if '_' in mail_id else "?"
            btn_text = f"📧 Mail {mail_num}: {mail_data['email'][:20]}..."
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f'view_mail_{mail_id}')])
        
        keyboard.append([InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"📨 *Mailleriniz* ({len(mails)} adet)\n\n"
            f"Kontrol etmek istediğiniz maili seçin:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif query.data == 'use_vip_key':
        await query.edit_message_text(
            "🔑 *VIP Key Kullan*\n\n"
            "VIP key'inizi gönderin:\n\n"
            "Örnek: `vip-key-email-bot-xxxxxxxxxxxxxxx`\n\n"
            "VIP olunca 10 mail oluşturabilirsiniz!\n\n"
            "İptal etmek için /start yazın",
            parse_mode='Markdown'
        )
        context.user_data['awaiting_vip_key'] = True
    
    elif query.data.startswith('view_mail_'):
        mail_id = query.data.replace('view_mail_', '')
        
        if str(user_id) not in user_mails or mail_id not in user_mails[str(user_id)]:
            await query.edit_message_text("❌ Mail bulunamadı!")
            
            # Ana menü butonu ekle
            keyboard = [[InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text("Ana menüye dönmek için:", reply_markup=reply_markup)
            return
        
        mail_data = user_mails[str(user_id)][mail_id]
        email = mail_data['email']
        
        # Bu mail için gelen kutusunu kontrol et
        new_mails = check_single_mail(user_id, mail_id)
        
        # Mail detaylarını göster
        total_messages = len(mail_data['messages'])
        last_checked = mail_data.get('last_checked', 'Hiç kontrol edilmedi')
        
        response = f"""
📧 *Mail Detayları*

🆔 *Mail No:* {mail_id.split('_')[1] if '_' in mail_id else '?'}
📧 *Adres:* `{email}`
📅 *Oluşturulma:* {mail_data['created_at'][:19]}
📬 *Toplam Mesaj:* {total_messages}
🔍 *Son Kontrol:* {last_checked[:19] if last_checked else 'Hiç'}

"""
        
        if new_mails:
            response += f"✅ *{len(new_mails)} yeni mail geldi!*\n\n"
            for mail in new_mails[-3:]:  # Son 3 maili göster
                response += f"• *Gönderen:* {mail['sender']}\n"
                if mail['code']:
                    response += f"  🔐 *KOD:* `{mail['code']}`\n"
                response += f"  *Konu:* {mail['subject'][:30]}...\n"
                response += "─" * 20 + "\n"
        elif total_messages > 0:
            response += f"📭 *Son Mailler:*\n\n"
            for mail in mail_data['messages'][-3:]:  # Son 3 maili göster
                response += f"• *Gönderen:* {mail['sender']}\n"
                if mail.get('code'):
                    response += f"  🔐 *KOD:* `{mail['code']}`\n"
                response += f"  *Konu:* {mail['subject'][:30]}...\n"
                response += "─" * 20 + "\n"
        else:
            response += "\n📭 *Gelen kutusu boş*"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Maili Kontrol Et", callback_data=f'check_mail_{mail_id}'),
             InlineKeyboardButton("🗑️ Maili Sil", callback_data=f'delete_mail_{mail_id}')],
            [InlineKeyboardButton("📨 Tüm Maillerim", callback_data='my_mails'),
             InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(response, 
                                     reply_markup=reply_markup,
                                     parse_mode='Markdown')
    
    elif query.data.startswith('check_mail_'):
        mail_id = query.data.replace('check_mail_', '')
        
        await query.edit_message_text("⏳ *Mail kontrol ediliyor...*", parse_mode='Markdown')
        
        # Maili kontrol et
        new_mails = check_single_mail(user_id, mail_id)
        
        if new_mails:
            response = f"✅ *{len(new_mails)} yeni mail bulundu!*\n\n"
            for mail in new_mails:
                response += f"• *Gönderen:* {mail['sender']}\n"
                response += f"  *Konu:* {mail['subject'][:50]}\n"
                if mail['code']:
                    response += f"  🔐 *KOD:* `{mail['code']}`\n"
                response += "─" * 30 + "\n"
        else:
            response = "📭 *Yeni mail bulunamadı*"
        
        keyboard = [
            [InlineKeyboardButton("📧 Mail Detayları", callback_data=f'view_mail_{mail_id}')],
            [InlineKeyboardButton("📨 Maillerim", callback_data='my_mails'),
             InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(response, 
                                     reply_markup=reply_markup,
                                     parse_mode='Markdown')
    
    elif query.data.startswith('delete_mail_'):
        mail_id = query.data.replace('delete_mail_', '')
        
        if str(user_id) in user_mails and mail_id in user_mails[str(user_id)]:
            deleted_email = user_mails[str(user_id)][mail_id]['email']
            del user_mails[str(user_id)][mail_id]
            save_data()
            
            await query.edit_message_text(f"✅ Mail `{deleted_email}` başarıyla silindi!")
            
            # Ana menü butonu ekle
            keyboard = [[InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text("Ana menüye dönmek için:", reply_markup=reply_markup)
        else:
            await query.edit_message_text("❌ Mail bulunamadı!")
    
    elif query.data == 'help':
        help_text = """
🤖 *Mail Bot Yardım*

*Komutlar:*
/start - Botu başlat
/mails - Maillerimi listele
/vip - VIP bilgileri
/help - Yardım menüsü

*Mail Limitleri:*
• Ücretsiz kullanıcılar: 2 mail hakkı
• VIP kullanıcılar: 10 mail hakkı
• Her mailin ayrı gelen kutusu

*VIP Sistemi:*
VIP olmak için VIP key'e ihtiyacınız var.
Key kullanmak için /start yazıp "VIP Key Kullan" butonuna tıklayın.

*Admin Komutları (Sadece Yetkililer):*
/admin - Admin paneli
/newvipkey - Yeni VIP key oluştur

✨ *Geliştirici:* @Scorpion292439
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
        limit_text = "10 mail" if is_vip else "2 mail"
        
        status_text = f"""
📊 *Hesap Durumunuz*

👤 *Durum:* {status}
📧 *Mail Sayısı:* {current}/{limit}
🎯 *Limit:* {limit_text}
📅 *Katılma Tarihi:* {users_data.get(str(user_id), {}).get('joined_at', 'Bilinmiyor')[:10]}

"""
        
        if is_vip:
            vip_until = users_data[str(user_id)].get('vip_until', '')
            if vip_until:
                status_text += f"⏰ *VIP Bitiş:* {vip_until[:10]}\n"
        
        status_text += f"\n{'✅ Yeni mail oluşturabilirsiniz' if can_create else '❌ Mail limitiniz doldu'}"
        
        keyboard = [
            [InlineKeyboardButton("📧 Yeni Mail", callback_data='create_mail')],
            [InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(status_text, 
                                     reply_markup=reply_markup,
                                     parse_mode='Markdown')
    
    elif query.data == 'admin_panel':
        if user_id != ADMIN_ID:
            await query.edit_message_text("❌ Bu işlemi yapma yetkiniz yok!")
            return
        
        # Admin paneli göster
        keyboard = [
            [InlineKeyboardButton("👥 Kullanıcı Listesi", callback_data='admin_users')],
            [InlineKeyboardButton("📊 İstatistikler", callback_data='admin_stats')],
            [InlineKeyboardButton("🔑 VIP Key Oluştur", callback_data='admin_create_key')],
            [InlineKeyboardButton("📢 Duyuru Yap", callback_data='admin_broadcast')],
            [InlineKeyboardButton("⛔ Ban İşlemleri", callback_data='admin_ban'),
             InlineKeyboardButton("🗑️ Temizlik", callback_data='admin_cleanup')],
            [InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text("⚡ *Admin Paneli*\n\nBir işlem seçin:",
                                     reply_markup=reply_markup,
                                     parse_mode='Markdown')
    
    elif query.data == 'main_menu':
        # Ana menüyü göster
        await show_main_menu(user_id, username, query=query)

# Admin buton handler'ı
async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    username = query.from_user.username or str(user_id)
    
    if user_id != ADMIN_ID:
        await query.edit_message_text("❌ Bu işlemi yapma yetkiniz yok!")
        return
    
    # Admin işlemlerini tek bir handler'da topladık
    if query.data == 'admin_users':
        if not users_data:
            await query.edit_message_text("📭 Henüz kayıtlı kullanıcı yok.")
            
            keyboard = [[InlineKeyboardButton("🔙 Admin Paneli", callback_data='admin_panel')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text("Admin paneline dönmek için:", reply_markup=reply_markup)
            return
        
        response = "👥 *Kullanıcı Listesi:*\n\n"
        for uid, data in list(users_data.items())[:20]:
            vip_status = "🎖️ VIP" if data.get('is_vip', False) else "👤 Free"
            mail_count = get_user_mail_count(int(uid))
            mail_limit = VIP_MAIL_LIMIT if data.get('is_vip', False) else FREE_MAIL_LIMIT
            response += f"• *ID:* `{uid}`\n"
            response += f"  *Kullanıcı:* @{data.get('username', 'N/A')}\n"
            response += f"  *Durum:* {vip_status}\n"
            response += f"  *Mail:* {mail_count}/{mail_limit} adet\n"
            response += f"  *Katılma:* {data.get('joined_at', 'N/A')[:10]}\n"
            response += "─" * 30 + "\n"
        
        keyboard = [
            [InlineKeyboardButton("🔙 Admin Paneli", callback_data='admin_panel'),
             InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(response, 
                                     reply_markup=reply_markup,
                                     parse_mode='Markdown')
    
    elif query.data == 'admin_stats':
        total_users = len(users_data)
        total_banned = len(banned_users)
        vip_users = sum(1 for u in users_data.values() if u.get('is_vip', False))
        total_mails = sum(len(mails) for mails in user_mails.values())
        active_keys = sum(1 for k in vip_keys.values() if datetime.fromisoformat(k['expires_at'].replace('Z', '+00:00')) > datetime.now())
        
        response = f"""
📊 *Bot İstatistikleri*

👥 Toplam Kullanıcı: *{total_users}*
🎖️ VIP Kullanıcı: *{vip_users}* ({VIP_MAIL_LIMIT} mail)
👤 Ücretsiz Kullanıcı: *{total_users - vip_users}* ({FREE_MAIL_LIMIT} mail)

📧 Toplam Mail: *{total_mails}*
🔑 Aktif VIP Key: *{active_keys}*
⛔ Banlı Kullanıcı: *{total_banned}*

🕒 Son Güncelleme: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        keyboard = [
            [InlineKeyboardButton("🔙 Admin Paneli", callback_data='admin_panel'),
             InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(response, 
                                     reply_markup=reply_markup,
                                     parse_mode='Markdown')
    
    elif query.data == 'admin_create_key':
        await query.edit_message_text(
            "🔑 *Yeni VIP Key Oluştur*\n\n"
            "Kullanım: /newvipkey <gün> <max_kullanım>\n"
            "Örnek: `/newvipkey 30 5` - 30 günlük, 5 kişilik key\n\n"
            "VIP key ile kullanıcılar 10 mail oluşturabilir!\n\n"
            "İptal etmek için /admin yazın",
            parse_mode='Markdown'
        )
    
    elif query.data == 'admin_broadcast':
        await query.edit_message_text("📢 *Duyuru Gönder*\n\nLütfen duyuru mesajınızı gönderin:\n\nİptal etmek için /admin yazın")
        context.user_data['awaiting_broadcast'] = True
    
    elif query.data == 'admin_ban':
        # Ban işlemleri menüsü
        keyboard = [
            [InlineKeyboardButton("🔨 Kullanıcı Banla", callback_data='ban_user')],
            [InlineKeyboardButton("🔓 Kullanıcı Banını Kaldır", callback_data='unban_user')],
            [InlineKeyboardButton("📋 Banlı Listesi", callback_data='banned_users_list')],
            [InlineKeyboardButton("🔙 Admin Paneli", callback_data='admin_panel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text("⛔ *Ban İşlemleri*\n\nBir işlem seçin:",
                                     reply_markup=reply_markup,
                                     parse_mode='Markdown')
    
    elif query.data == 'ban_user':
        await query.edit_message_text(
            "🔨 *Kullanıcı Banla*\n\n"
            "Banlamak istediğiniz kullanıcı ID'sini gönderin:\n\n"
            "Örnek: `1234567890`\n\n"
            "İptal etmek için /admin yazın",
            parse_mode='Markdown'
        )
        context.user_data['awaiting_ban_user'] = True
    
    elif query.data == 'unban_user':
        await query.edit_message_text(
            "🔓 *Kullanıcı Banını Kaldır*\n\n"
            "Banını kaldırmak istediğiniz kullanıcı ID'sini gönderin:\n\n"
            "Örnek: `1234567890`\n\n"
            "İptal etmek için /admin yazın",
            parse_mode='Markdown'
        )
        context.user_data['awaiting_unban_user'] = True
    
    elif query.data == 'banned_users_list':
        if not banned_users:
            await query.edit_message_text("📭 Banlı kullanıcı yok.")
        else:
            response = "⛔ *Banlı Kullanıcılar:*\n\n"
            for uid, reason in list(banned_users.items())[:20]:
                response += f"• *ID:* `{uid}`\n"
                response += f"  *Sebep:* {reason}\n"
                response += "─" * 20 + "\n"
            
            await query.edit_message_text(response, parse_mode='Markdown')
        
        keyboard = [[InlineKeyboardButton("🔙 Admin Paneli", callback_data='admin_panel')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Devam etmek için:", reply_markup=reply_markup)
    
    elif query.data == 'admin_cleanup':
        # Eski verileri temizle
        cleaned = 0
        current_time = datetime.now()
        
        for uid in list(user_mails.keys()):
            if uid not in users_data:
                del user_mails[uid]
                cleaned += 1
        
        await query.edit_message_text(f"✅ Temizlik tamamlandı! {cleaned} eski kayıt silindi.")
        
        keyboard = [
            [InlineKeyboardButton("🔙 Admin Paneli", callback_data='admin_panel'),
             InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Devam etmek için:", reply_markup=reply_markup)
    
    elif query.data == 'main_menu':
        # Ana menüye dön
        await show_main_menu(user_id, username, query=query)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.message.text.strip()
    
    # VIP key kullanımı
    if context.user_data.get('awaiting_vip_key'):
        context.user_data['awaiting_vip_key'] = False
        
        success, result_msg = use_vip_key(user_id, message_text)
        
        if success:
            # Kullanıcıyı ana menüye yönlendir
            await show_main_menu(user_id, update.effective_user.username or str(user_id), message=update.message)
            await update.message.reply_text(
                f"✅ {result_msg}",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(f"{result_msg}\n\nTekrar denemek için /start yazın.")
        return
    
    # Admin broadcast mesajı
    if user_id == ADMIN_ID and context.user_data.get('awaiting_broadcast'):
        context.user_data['awaiting_broadcast'] = False
        
        sent = 0
        failed = 0
        
        await update.message.reply_text("📢 Duyuru gönderiliyor...")
        
        for uid in users_data.keys():
            try:
                await context.bot.send_message(
                    chat_id=int(uid), 
                    text=f"📢 *BOT DUYURUSU*\n\n{message_text}\n\n_@Scorpion292439_",
                    parse_mode='Markdown'
                )
                sent += 1
                await asyncio.sleep(0.1)
            except:
                failed += 1
        
        await update.message.reply_text(
            f"✅ Duyuru tamamlandı!\n\n"
            f"✓ Gönderilen: {sent}\n"
            f"✗ Başarısız: {failed}\n\n"
            f"Admin paneli için /admin yazın"
        )
        return
    
    # Admin ban kullanıcı
    if user_id == ADMIN_ID and context.user_data.get('awaiting_ban_user'):
        context.user_data['awaiting_ban_user'] = False
        
        try:
            ban_user_id = int(message_text)
            banned_users[str(ban_user_id)] = f"Admin tarafından {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            save_data()
            
            await update.message.reply_text(
                f"✅ Kullanıcı `{ban_user_id}` başarıyla banlandı!\n\n"
                f"Admin paneli için /admin yazın"
            )
        except ValueError:
            await update.message.reply_text("❌ Geçersiz kullanıcı ID'si!")
        return
    
    # Admin unban kullanıcı
    if user_id == ADMIN_ID and context.user_data.get('awaiting_unban_user'):
        context.user_data['awaiting_unban_user'] = False
        
        try:
            unban_user_id = str(message_text)
            if unban_user_id in banned_users:
                del banned_users[unban_user_id]
                save_data()
                
                await update.message.reply_text(
                    f"✅ Kullanıcı `{unban_user_id}` banı kaldırıldı!\n\n"
                    f"Admin paneli için /admin yazın"
                )
            else:
                await update.message.reply_text("❌ Bu kullanıcı zaten banlı değil!")
        except:
            await update.message.reply_text("❌ Geçersiz kullanıcı ID'si!")
        return
    
    # Normal mesajları işle
    await update.message.reply_text("Komutlar için /start yazın.")

# Komutlar
async def mails_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or str(user_id)
    
    if str(user_id) not in user_mails or not user_mails[str(user_id)]:
        await update.message.reply_text("📭 Henüz mail adresiniz yok. Önce mail oluşturun!")
        return
    
    mails = user_mails[str(user_id)]
    keyboard = []
    
    for mail_id, mail_data in mails.items():
        mail_num = mail_id.split('_')[1] if '_' in mail_id else "?"
        btn_text = f"📧 Mail {mail_num}: {mail_data['email'][:20]}..."
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f'view_mail_{mail_id}')])
    
    keyboard.append([InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📨 *Mailleriniz* ({len(mails)} adet)\n\nKontrol etmek istediğiniz maili seçin:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or str(user_id)
    
    if str(user_id) not in users_data:
        await update.message.reply_text("Önce /start komutu ile başlayın!")
        return
    
    is_vip = users_data[str(user_id)].get('is_vip', False)
    mail_count = get_user_mail_count(user_id)
    
    if is_vip:
        vip_until = users_data[str(user_id)].get('vip_until', '')
        vip_info = f"\n⏰ *VIP Bitiş:* {vip_until[:10]}" if vip_until else ""
        
        response = f"""
🎖️ *VIP Hesabınız*

✅ Zaten VIP üyesisiniz!
📧 *Mail Limiti:* 10 adet
📊 *Mevcut Mail:* {mail_count}/10
{vip_info}

VIP key'inizi arkadaşlarınızla paylaşabilirsiniz!
        """
    else:
        response = f"""
🔑 *VIP Sistemi*

📊 *Mevcut Durum:* Ücretsiz (2 mail)
📧 *Kullanılan Mail:* {mail_count}/2

🎖️ *VIP Avantajları:*
• 10 mail oluşturma hakkı (ücretsizde 2)
• Her mailin ayrı gelen kutusu
• Öncelikli destek

💰 *VIP olmak için:*
VIP key almanız gerekiyor.
Bir VIP key'iniz varsa butona tıklayın:
        """
        
        keyboard = [
            [InlineKeyboardButton("🔑 VIP Key Kullan", callback_data='use_vip_key')],
            [InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(response, 
                                       reply_markup=reply_markup,
                                       parse_mode='Markdown')
        return
    
    keyboard = [[InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(response, 
                                   reply_markup=reply_markup,
                                   parse_mode='Markdown')

async def newvipkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Bu komutu kullanma yetkiniz yok!")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text(
            "❌ Kullanım: /newvipkey <gün> <max_kullanım>\n"
            "Örnek: `/newvipkey 30 5` - 30 günlük, 5 kişilik key\n\n"
            "VIP key ile kullanıcılar 10 mail oluşturabilir!",
            parse_mode='Markdown'
        )
        return
    
    try:
        days = int(context.args[0])
        max_uses = int(context.args[1])
        
        if days <= 0 or max_uses <= 0:
            await update.message.reply_text("❌ Gün ve kullanım sayısı pozitif olmalı!")
            return
        
        key = generate_vip_key(days, max_uses)
        
        await update.message.reply_text(
            f"✅ *Yeni VIP Key Oluşturuldu!*\n\n"
            f"🔑 *Key:* `{key}`\n"
            f"📅 *Süre:* {days} gün\n"
            f"👥 *Max Kullanım:* {max_uses} kişi\n\n"
            f"*Kullanım:*\n"
            f"1. /start yaz\n"
            f"2. 'VIP Key Kullan' butonuna tıkla\n"
            f"3. Bu key'i gönder\n\n"
            f"*Özellik:* VIP olanlar 10 mail oluşturabilir!\n\n"
            f"Admin paneli için /admin yazın",
            parse_mode='Markdown'
        )
    except ValueError:
        await update.message.reply_text("❌ Geçersiz sayı formatı!")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Bu komutu kullanma yetkiniz yok!")
        return
    
    keyboard = [
        [InlineKeyboardButton("👥 Kullanıcı Listesi", callback_data='admin_users')],
        [InlineKeyboardButton("📊 İstatistikler", callback_data='admin_stats')],
        [InlineKeyboardButton("🔑 VIP Key Oluştur", callback_data='admin_create_key')],
        [InlineKeyboardButton("📢 Duyuru Yap", callback_data='admin_broadcast')],
        [InlineKeyboardButton("⛔ Ban İşlemleri", callback_data='admin_ban'),
         InlineKeyboardButton("🗑️ Temizlik", callback_data='admin_cleanup')],
        [InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("⚡ *Admin Paneli*\n\nBir işlem seçin:",
                                   reply_markup=reply_markup,
                                   parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🤖 *Mail Bot Yardım*

*Ana Komutlar:*
/start - Botu başlat ve ana menüyü aç
/mails - Maillerimi görüntüle
/vip - VIP durumunu kontrol et
/help - Bu yardım mesajını göster

*Mail Özellikleri:*
• Ücretsiz kullanıcılar: 2 mail hakkı
• VIP kullanıcılar: 10 mail hakkı
• Her mailin ayrı gelen kutusu
• Doğrulama kodları otomatik yakalanır

*VIP Sistemi:*
VIP olmak için VIP key'e ihtiyacınız var.
Key kullanmak için /start yazıp "VIP Key Kullan" butonuna tıklayın.

*Sorun Çözme:*
• Butonlar çalışmıyorsa /start yazın
• Mail oluşmuyorsa biraz bekleyip tekrar deneyin
• Hata alıyorsanız /start ile yeniden başlayın

✨ *Geliştirici:* @Scorpion292439
    """
    
    keyboard = [[InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(help_text, 
                                   reply_markup=reply_markup,
                                   parse_mode='Markdown')

# Ana fonksiyon
def main():
    # Banner göster
    os.system('cls' if os.name == 'nt' else 'clear')
    print(Fore.RED + Style.BRIGHT + pyfiglet.figlet_format("MAIL BOT v5.0"))
    print(Fore.CYAN + Style.BRIGHT + "Mail Bot v5.0 - Limit Edition")
    print(Fore.MAGENTA + "                                   █ @Scorpion292439 █\n")
    
    # İstatistikleri göster
    total_users = len(users_data)
    vip_users = sum(1 for u in users_data.values() if u.get('is_vip', False))
    total_mails = sum(len(mails) for mails in user_mails.values())
    active_keys = sum(1 for k in vip_keys.values() if datetime.fromisoformat(k['expires_at'].replace('Z', '+00:00')) > datetime.now())
    
    print(Fore.GREEN + f"✓ Bot başlatılıyor...")
    print(Fore.YELLOW + f"✓ Admin ID: {ADMIN_ID}")
    print(Fore.YELLOW + f"✓ Kayıtlı kullanıcı: {total_users}")
    print(Fore.CYAN + f"✓ VIP kullanıcı: {vip_users}")
    print(Fore.CYAN + f"✓ Toplam mail: {total_mails}")
    print(Fore.MAGENTA + f"✓ Aktif VIP key: {active_keys}")
    print(Fore.RED + f"✗ Free limit: {FREE_MAIL_LIMIT} mail")
    print(Fore.GREEN + f"✓ VIP limit: {VIP_MAIL_LIMIT} mail")
    print(Fore.CYAN + "═" * 50)
    
    # Bot'u başlat
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Komut handler'ları
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mails", mails_command))
    app.add_handler(CommandHandler("vip", vip_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("newvipkey", newvipkey_command))
    
    # Callback query handler'ları
    app.add_handler(CallbackQueryHandler(button_handler, pattern='^(create_mail|my_mails|use_vip_key|help|status|main_menu|admin_panel|view_mail_.*|check_mail_.*|delete_mail_.*)$'))
    
    # Admin callback'leri için ayrı handler
    app.add_handler(CallbackQueryHandler(admin_button_handler, pattern='^(admin_users|admin_stats|admin_create_key|admin_broadcast|admin_ban|admin_cleanup|ban_user|unban_user|banned_users_list)$'))
    
    # Mesaj handler'ı
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print(Fore.GREEN + "✓ Bot çalışıyor...")
    print(Fore.CYAN + "═" * 50)
    print(Fore.YELLOW + "Kullanıcılar için: /start")
    print(Fore.YELLOW + "Admin için: /admin")
    print(Fore.CYAN + "═" * 50)
    
    # Bot'u çalıştır
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()