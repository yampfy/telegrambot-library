import telebot
from telebot import types
import sqlite3
import functools

TOKEN = 'token'
bot = telebot.TeleBot(TOKEN)
CURRENT_PAGE = {}
user_data = {}

def create_connection(user_id):
    conn = sqlite3.connect(f'books_{user_id}.db')
    cursor = conn.cursor()
    create_books_table(cursor)
    conn.commit()
    return conn

def create_books_table(cursor):
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            review TEXT NOT NULL,
            rating REAL NOT NULL
        )
    ''')

def send_welcome(message):
    user_id = message.chat.id
    conn = create_connection(user_id)
    bot.send_message(user_id, "Привет! Я бот для отзывов о книгах. Чтобы начать, используй /start.")
    send_inline_keyboard(user_id)

def send_inline_keyboard(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    books_button = types.InlineKeyboardButton("📚 Книги", callback_data='books')
    add_button = types.InlineKeyboardButton("➕ Добавить отзыв", callback_data='add_review')
    delete_button = types.InlineKeyboardButton("🗑️ Удалить отзыв", callback_data='delete_review')
    edit_button = types.InlineKeyboardButton("✏️ Редактировать отзыв", callback_data='edit_review')
    markup.add(books_button, add_button)
    markup.add(delete_button, edit_button)
    bot.send_message(chat_id, "Выберите действие:", reply_markup=markup)

def show_default_keyboard(bot, chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    books_button = types.InlineKeyboardButton("📚 Книги", callback_data='books')
    add_button = types.InlineKeyboardButton("➕ Добавить отзыв", callback_data='add_review')
    delete_button = types.InlineKeyboardButton("🗑️ Удалить отзыв", callback_data='delete_review')
    edit_button = types.InlineKeyboardButton("✏️ Редактировать отзыв", callback_data='edit_review')

    markup.add(books_button, add_button, delete_button, edit_button)
    bot.send_message(chat_id, "Выберите действие:", reply_markup=markup)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "Привет! Я бот-библиотека книг с отзывами.\n"
        "Чтобы посмотреть список книг, используй команду /books.\n"
        "Чтобы добавить отзыв, используй команду /add_review.\n"
        "Чтобы удалить отзыв, используй команду /delete_review."
    )
    bot.reply_to(message, welcome_text)
    send_inline_keyboard(message.chat.id)

@bot.message_handler(commands=['books'])
def send_books(bot, message):
    conn = create_connection(message.chat.id)
    cursor = conn.cursor()

    cursor.execute('SELECT title, review, rating FROM books')
    books_data = cursor.fetchall()

    conn.close()

    if books_data:
        items_per_page = 5
        current_page = CURRENT_PAGE.get(message.chat.id, 0)
        paginated_books = paginate_list(books_data, current_page, items_per_page)

        books_text = "\n\n".join([f"📖 {title}\n📝 {review}\n⭐ Оценка: {rating}" for title, review, rating in paginated_books])
        pagination_markup = create_pagination_markup(current_page, len(books_data), items_per_page)

        bot.reply_to(message, f"Список книг:\n\n{books_text}", reply_markup=pagination_markup)
        show_default_keyboard(bot, message.chat.id)
        CURRENT_PAGE[message.chat.id] = current_page
    else:
        bot.reply_to(message, "В библиотеке пока нет книг.")
        show_default_keyboard(bot, message.chat.id)

@bot.message_handler(commands=['add_review'])
def add_review(message):
    bot.send_message(message.chat.id, "Введите название книги:")
    bot.register_next_step_handler(message, process_title_step)

def process_title_step(message):
    title = message.text
    bot.send_message(message.chat.id, f"Введите отзыв о книге '{title}':")
    bot.register_next_step_handler(message, process_review_step, title)

def process_review_step(message, title):
    user_id = message.chat.id
    review = message.text
    bot.send_message(user_id, f"Введите оценку книге '{title}' от 0.1 до 5:")
    bot.register_next_step_handler(message, process_rating_step, title, review)

def process_rating_step(message, title, review):
    chat_id = message.chat.id
    rating = message.text

    try:
        rating = float(rating)
        if rating < 0.1 or rating > 5:
            raise ValueError
        save_review(chat_id, title, review, rating)
        bot.reply_to(message, "Отлично! Ваш отзыв сохранен. Спасибо за ваши впечатления.")
    except ValueError:
        bot.reply_to(message, "Оценка должна быть числом от 0.1 до 5. Попробуйте еще раз.")
        process_review_step(message, title)

    user_data[chat_id] = {}
    show_default_keyboard(bot, chat_id)

def save_review(chat_id, title, review, rating):
    conn = create_connection(chat_id)
    cursor = conn.cursor()

    cursor.execute('INSERT INTO books (title, review, rating) VALUES (?, ?, ?)', (title, review, rating))
    conn.commit()

    conn.close()

@bot.message_handler(commands=['delete_review'])
def delete_review(message):
    bot.send_message(message.chat.id, "Введите название книги, отзыв которой вы хотите удалить:")
    bot.register_next_step_handler(message, process_delete_review, message.chat.id)

def process_delete_review(message, user_id):
    title_to_delete = message.text
    conn = create_connection(user_id)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM books WHERE title=?', (title_to_delete,))
    conn.commit()
    conn.close()
    bot.reply_to(message, f"Отзыв о книге '{title_to_delete}' успешно удален.")
    show_default_keyboard(bot, user_id)

@bot.message_handler(commands=['edit_review'])
def edit_review(message):
    bot.send_message(message.chat.id, "Введите название книги, отзыв которой вы хотите отредактировать:")
    bot.register_next_step_handler(message, process_edit_review)

def process_edit_review(message):
    title_to_edit = message.text

    conn = create_connection(message.chat.id)
    cursor = conn.cursor()

    cursor.execute('SELECT title, review, rating FROM books WHERE title=?', (title_to_edit,))
    book_data = cursor.fetchone()

    conn.close()

    if book_data:
        title, review, rating = book_data
        bot.send_message(message.chat.id, f"Текущий отзыв о книге '{title}':\n📝 {review}\n⭐ Rating: {rating}")
        bot.send_message(message.chat.id, "Введите новый отзыв:")
        bot.register_next_step_handler(message, process_new_review, title)
    else:
        bot.reply_to(message, f"Книги с названием '{title_to_edit}' нет в библиотеке.")
        show_default_keyboard(bot, message.chat.id)

def process_new_review(message, title):
    new_review = message.text
    bot.send_message(message.chat.id, f"Введите новую оценку книге '{title}' от 0.1 до 5:")
    bot.register_next_step_handler(message, process_new_rating, title, new_review)

def process_new_rating(message, title, new_review):
    new_rating = message.text

    try:
        new_rating = float(new_rating)
        if new_rating < 0.1 or new_rating > 5:
            raise ValueError
        conn = create_connection(message.chat.id)
        cursor = conn.cursor()

        cursor.execute('UPDATE books SET review=?, rating=? WHERE title=?', (new_review, new_rating, title))
        conn.commit()

        conn.close()

        bot.reply_to(message, f"Отзыв о книге '{title}' успешно отредактирован:\n📝 {new_review}\n⭐ Rating: {new_rating}")
    except ValueError:
        bot.reply_to(message, "Оценка должна быть числом от 0.1 до 5. Попробуйте еще раз.")
        process_new_review(message, title)

    show_default_keyboard(bot, message.chat.id)

def paginate_list(data_list, current_page, items_per_page):
    start_index = current_page * items_per_page
    end_index = start_index + items_per_page
    return data_list[start_index:end_index]

def create_pagination_markup(current_page, total_items, items_per_page):
    total_pages = (total_items + items_per_page - 1) // items_per_page
    markup = types.InlineKeyboardMarkup()

    if current_page > 0:
        prev_button = types.InlineKeyboardButton("⬅️ Пред.", callback_data=f'page,{current_page-1}')
        markup.add(prev_button)

    if (current_page + 1) < total_pages:
        next_button = types.InlineKeyboardButton("След. ➡️", callback_data=f'page,{current_page+1}')
        markup.add(next_button)

    return markup

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data.startswith('page,'):
        page = int(call.data.split(',')[1])
        CURRENT_PAGE[call.message.chat.id] = page
        send_books(bot, call.message)
    elif call.data == 'books':
        send_books(bot, call.message)
    elif call.data == 'add_review':
        add_review(call.message)
    elif call.data == 'delete_review':
        delete_review(call.message)
    elif call.data == 'edit_review':
        edit_review(call.message)

if __name__ == '__main__':
    bot.polling(none_stop=True)
