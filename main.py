from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session
import shelve
import os
import requests
import pandas as pd
import openpyxl
from flask_mail import Mail, Message
import uuid
from werkzeug.security import generate_password_hash, check_password_hash

i = 5

DB_FILE = 'admin_database.db'
REWARDS_DB = 'rewards.db'
DATABASE_CARTS = 'carts.db'

app = Flask(__name__)
app.secret_key = 'your_secret_key'
DATABASE = "inventory.db"
STATIC_IMAGES_PATH = os.path.join('static', 'images')
EXPORT_PATH = os.path.join('exports')
EXPORT_FILE = os.path.join(EXPORT_PATH, 'inventory_export.xlsx')

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config[
    'MAIL_USERNAME'] = 'samplebookshopnyp@gmail.com'  # Replace with your email
app.config[
    'MAIL_PASSWORD'] = 'vtxd xdyr gkkf kuys'  # Replace with your email password

mail = Mail(app)


# Initialize databases
def initialize_databases():
    # Initialize sales database
    with shelve.open(DATABASE, writeback=True) as db:
        if 'sales' not in db:
            db['sales'] = {}  # Key: ISBN, Value: List of sales transactions

    # Initialize rewards database
    with shelve.open(REWARDS_DB, flag='c', writeback=True) as db:
        if len(db) == 0:
            db['Sample Reward'] = {
                "points": 100,
                "quantity": 10,
                "image_url": ""
            }
            db['Premium Reward'] = {
                "points": 500,
                "quantity": 5,
                "image_url": ""
            }


@app.route('/simulate_purchase/<isbn>', methods=['POST'])
def simulate_purchase(isbn):
    with shelve.open(DATABASE, writeback=True) as db:
        books = db.get('books', {})
        sales = db.get('sales', {})

        if isbn in books:
            books[isbn]['stock'] -= 1
            flash(
                f"Simulated purchase for '{books[isbn]['title']}'. New stock: {books[isbn]['stock']}",
                'info')

            # Log the sale
            if isbn not in sales:
                sales[isbn] = []
            sales[isbn].append({
                "date": pd.Timestamp.now().strftime("%Y-%m-%d"),
                "quantity": 1
            })
            db['sales'] = sales

            # Stock alert
            if books[isbn]['stock'] < books[isbn]['alert_stock']:
                reorder_quantity = books[isbn]['alert_stock'] * 2 - books[
                    isbn]['stock']
                msg = Message(
                    subject=f"Stock Alert: {books[isbn]['title']}",
                    sender='samplebookshopnyp@gmail.com',
                    recipients=['samplebookshopnyp@gmail.com'],
                    body=
                    (f"The stock for the book '{books[isbn]['title']}' has fallen below the predefined threshold.\n\n"
                     f"Current Stock: {books[isbn]['stock']}\n"
                     f"Suggested Reorder Quantity: {reorder_quantity}\n\n"
                     f"Please take the necessary steps to restock this item."))
                mail.send(msg)
                flash(f"Stock alert email sent for '{books[isbn]['title']}'.",
                      'info')

    return redirect(url_for('catalog_admin'))


@app.route('/generate_report')
def generate_report():
    with shelve.open(DATABASE) as db:
        books = db.get('books', {})
        sales = db.get('sales', {})

        # Prepare data for the report
        report_data = []
        for isbn, book in books.items():
            monthly_sales = sum(sale['quantity']
                                for sale in sales.get(isbn, [])
                                if pd.Timestamp(sale['date']).month ==
                                pd.Timestamp.now().month)
            reorder_quantity = 0
            if book['stock'] < book['alert_stock']:
                reorder_quantity = book['alert_stock'] * 2 - book['stock']

            report_data.append({
                "ISBN": isbn,
                "Title": book['title'],
                "Current Stock": book['stock'],
                "Monthly Sales": monthly_sales,
                "Reorder Recommendation": reorder_quantity
            })

        # Create a DataFrame
        df = pd.DataFrame(report_data)

        # Export to Excel
        if not os.path.exists(EXPORT_PATH):
            os.makedirs(EXPORT_PATH)
        report_file = os.path.join(
            EXPORT_PATH,
            f"inventory_report_{pd.Timestamp.now().strftime('%Y-%m')}.xlsx")
        df.to_excel(report_file, index=False)

    return send_file(
        report_file,
        as_attachment=True,
        download_name=
        f"inventory_report_{pd.Timestamp.now().strftime('%Y-%m')}.xlsx")


# Helper function to initialize the database
def get_db():
    with shelve.open(DATABASE, writeback=True) as db:
        if 'books' not in db:
            db['books'] = {}
        return db


@app.route('/catalog_admin')
def catalog_admin():
    """Render the catalog page with book data for admin."""
    if not session.get('user_id') or session.get('role') != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('user_catalog'))

    with shelve.open(DATABASE) as db:
        books = db.get('books', {})
    return render_template('catalogadmin.html', books=books)


@app.route('/catalog_user')
def user_catalog():
    """Render the catalog page for users."""
    if not session.get('user_id'):
        flash('Please login to view the catalog.', 'warning')
        return redirect(url_for('login'))

    with shelve.open(DATABASE) as db:
        books = db.get('books', {})
    return render_template('usercatalog.html', books=books, exclude_part=True)


@app.route('/add', methods=['GET', 'POST'])
def add_book():
    """Add a new book."""
    if request.method == 'POST':
        required_fields = [
            'isbn', 'bookTitle', 'price', 'currentStock', 'alertStock'
        ]
        for field in required_fields:
            if not request.form.get(field):
                flash(f"{field} is required.", "danger")
                return redirect(url_for('add_book'))

        new_book = {
            'isbn': request.form['isbn'],
            'title': request.form['bookTitle'],
            'price': float(request.form['price']),
            'stock': int(request.form['currentStock']),
            'alert_stock': int(request.form['alertStock']),
            'eco_friendly': 'ecoFriendly' in request.form,
            'synopsis': request.form['synopsis'],
            'category': request.form.get('category', 'Physical'),
            'image': 'placeholder.png',
        }

        if 'image' in request.files and request.files['image'].filename:
            image = request.files['image']
            filename = image.filename
            image.save(os.path.join(STATIC_IMAGES_PATH, filename))
            new_book['image'] = filename

        with shelve.open(DATABASE, writeback=True) as db:
            db['books'][new_book['isbn']] = new_book

        flash("New book added successfully!", "success")
        return redirect(url_for('catalog_admin'))

    return render_template('createeditbook.html')


@app.route('/fetch_isbn', methods=['POST'])
def fetch_isbn():
    """Fetch book details from OpenLibrary API based on ISBN."""
    isbn = request.json.get('isbn')
    if not isbn:
        return jsonify({"error": "No ISBN provided"}), 400

    print(f"Fetching details for ISBN: {isbn}")  # Debugging log

    url = f"https://openlibrary.org/isbn/{isbn}.json"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        title = data.get("title", "")
        description = data.get("description", "")
        if isinstance(description, dict):
            description = description.get("value", "")

        return jsonify({"title": title, "synopsis": description})

    return jsonify({"error": f"Book not found for ISBN {isbn}"}), 404


@app.route('/edit/<isbn>', methods=['GET', 'POST'])
def edit_book(isbn):
    """Edit an existing book."""
    with shelve.open(DATABASE, writeback=True) as db:
        books = db.get('books', {})
        book = books.get(isbn)

    if not book:
        flash("Book not found.", "danger")
        return redirect(url_for('catalog_admin'))

    if request.method == 'POST':
        book['title'] = request.form['bookTitle']
        book['price'] = float(request.form['price'])
        book['stock'] = int(request.form['currentStock'])
        book['alert_stock'] = int(request.form['alertStock'])
        book['eco_friendly'] = 'ecoFriendly' in request.form
        book['synopsis'] = request.form['synopsis']
        book['category'] = request.form.get('category', 'Physical')

        if 'image' in request.files and request.files['image'].filename:
            image = request.files['image']
            filename = image.filename
            image.save(os.path.join(STATIC_IMAGES_PATH, filename))
            book['image'] = filename

        with shelve.open(DATABASE, writeback=True) as db:
            db['books'][isbn] = book

        flash("Book updated successfully!", "success")
        return redirect(url_for('catalog_admin'))

    return render_template('editbook.html', book=book)


@app.route('/book/<isbn>')
def book_details(isbn):
    """Display detailed view of a specific book."""
    with shelve.open(DATABASE) as db:
        books = db.get('books', {})
        book = books.get(isbn)

    if not book:
        flash("Book not found.", "danger")
        return redirect(url_for('user_catalog'))

    return render_template('bookdetails.html', book=book)


@app.route('/filter_books', methods=['POST'])
def filter_books():
    """Filter books based on selected categories and eco-friendliness."""
    filters = request.json

    with shelve.open(DATABASE) as db:
        books = db.get('books', {})

        # If no filters are selected, return all books
        if filters.get('showAll', False):
            return jsonify({'books': list(books.values())})

        filtered_books = []

        for book in books.values():
            matches_category = ((filters.get('physicalBooks')
                                 and book.get('category') == 'Physical')
                                or (filters.get('ebooks')
                                    and book.get('category') == 'E-Book')
                                or (filters.get('magazines')
                                    and book.get('category') == 'Magazine'))
            matches_eco_friendly = not filters.get('ecoFriendly') or book.get(
                'eco_friendly', False)

            if matches_category and matches_eco_friendly:
                filtered_books.append(book)

    return jsonify({'books': filtered_books})


@app.route('/add_to_cart/<isbn>', methods=['POST'])
def add_to_cart(isbn):
    """Add a book to the temporary cart."""
    user_id = session.get('user_id')
    if not user_id:
        flash("Please login to add items to your cart.", "danger")
        return redirect(url_for('user_catalog'))

    with shelve.open(DATABASE) as books_db:
        books = books_db.get('books', {})
        if isbn not in books:
            flash("Book not found.", "danger")
            return redirect(url_for('user_catalog'))

        book = books[isbn]
        # Check if there's enough stock
        if book['stock'] < 1:
            flash("Sorry, this item is out of stock.", "danger")
            return redirect(url_for('user_catalog'))

        with shelve.open(DB_FILE, writeback=True) as users_db:
            user_data = users_db.get(user_id)
            if not user_data:
                flash("User not found.", "danger")
                return redirect(url_for('user_catalog'))

            cart = user_data.get('Cart', [])
            
            # Check if book already in cart
            book_in_cart = False
            for item in cart:
                if isinstance(item, dict) and item.get('isbn') == isbn:
                    if item['quantity'] + 1 > book['stock']:
                        flash("Sorry, not enough stock available.", "danger")
                        return redirect(url_for('user_catalog'))
                    item['quantity'] += 1
                    book_in_cart = True
                    break

            if not book_in_cart:
                cart.append({
                    'isbn': isbn,
                    'title': book['title'],
                    'price': book['price'],
                    'quantity': 1
                })

            user_data['Cart'] = cart
            users_db[user_id] = user_data
            flash(f"{book['title']} added to your cart.", "success")

    return redirect(url_for('user_catalog'))


@app.route('/delete/<isbn>', methods=['POST'])
def delete_book(isbn):
    """Delete a book."""
    with shelve.open(DATABASE, writeback=True) as db:
        books = db.get('books', {})
        if isbn in books:
            books.pop(isbn)
            flash("Book deleted successfully.", "success")
        else:
            flash("Book not found.", "danger")

    return redirect(url_for('catalog_admin'))


@app.route('/export_excel')
def export_excel():
    """Export the current book database to an Excel file."""
    with shelve.open(DATABASE) as db:
        books = db.get('books', {})
        if not books:
            flash("No data to export.", "danger")
            return redirect(url_for('catalog_admin'))

        df = pd.DataFrame.from_dict(books, orient='index')
        if not os.path.exists(EXPORT_PATH):
            os.makedirs(EXPORT_PATH)

        df.to_excel(EXPORT_FILE, index=False)

    return send_file(EXPORT_FILE,
                     as_attachment=True,
                     download_name="inventory_export.xlsx")


#don't touch files
# Function to add a new user
def add_user(name, email, password, role="user", points=0, cart=None):
    if cart is None:
        cart = []

    with shelve.open(DB_FILE) as db:
        # Check if email already exists
        for user_data in db.values():
            if user_data['Email'] == email:
                return None  # Email already exists

        user_id = str(uuid.uuid4())
        hashed_password = generate_password_hash(password)

        db[user_id] = {
            'Name': name,
            'Email': email,
            'Password': hashed_password,
            'Role': role,
            'Points': points,
            'Cart': cart
        }

    return user_id


# Function to get user by ID
def get_user(user_id):
    with shelve.open(DB_FILE) as db:
        return db.get(user_id, None)


# Function to update user
def update_user(user_id, updates):
    with shelve.open(DB_FILE) as db:
        if user_id in db:
            user_data = db[user_id]
            user_data.update(updates)
            db[user_id] = user_data
            return True
        return False


# Function to delete user
def delete_user(user_id):
    with shelve.open(DB_FILE) as db:
        if user_id in db:
            del db[user_id]
            return True
        return False


# Route to update a user
@app.route('/update_user/<user_id>', methods=['GET', 'POST'])
def update_user_page(user_id):
    if request.method == 'POST':
        data = request.form
        updates = {
            'Name': data.get('name'),
            'Email': data.get('email'),
            'Role': data.get('role'),
            'Points': int(data.get('points')) if data.get('points') else 0
        }
        updates = {
            key: value
            for key, value in updates.items()
            if value is not None and value != ''
        }

        if update_user(user_id, updates):
            return redirect(url_for('view_database'))
        return jsonify({'error': 'User not found'}), 404

    user_data = get_user(user_id)
    if not user_data:
        return jsonify({'error': 'User not found'}), 404

    return render_template('update_user.html', user=user_data, user_id=user_id)


# Route to delete a user
@app.route('/delete_user/<user_id>', methods=['POST'])
def delete_user_page(user_id):
    if delete_user(user_id):
        return redirect(url_for('view_database'))
    return jsonify({'error': 'User not found'}), 404


# Register route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.form
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        confirm_password = data.get('confirm_password')

        if not (name and email and password and confirm_password):
            return render_template('register.html',
                                   error="All fields are required!")

        if password != confirm_password:
            return render_template('register.html',
                                   error="Passwords do not match!")

        add_user(name, email, password, role="user")
        return redirect(url_for('login'))

    return render_template('register.html')


# Route to add a new user
@app.route('/add_user', methods=['GET', 'POST'])
def add_user_page():
    if request.method == 'POST':
        data = request.form
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        confirm_password = data.get('confirm_password')
        role = data.get('role')

        if not (name and email and password and confirm_password and role):
            return render_template('add_user.html',
                                   error="Missing required fields!")

        if password != confirm_password:
            return render_template('add_user.html',
                                   error="Passwords do not match!")

        user_id = add_user(name, email, password, role)
        if not user_id:
            return render_template('add_user.html',
                                   error="Email already exists!")

        return redirect(url_for('dashboard'))

    return render_template('add_user.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.form
        email = data.get('email', '').strip()
        password = data.get('password')
        with shelve.open(DB_FILE, 'c') as db:
            for user_id, user_data in db.items():
                if user_data.get('Email') == email:
                    if password and check_password_hash(user_data.get('Password', ''), password):
                        session['user_id'] = user_id
                        session['role'] = user_data.get('Role')
                        session['email'] = user_data.get('Email')  # Store email in session
                        session['points'] = user_data.get('Points', 0)  # Store points in session
                        if user_data.get('Role') == "admin":
                            return redirect(url_for('admin_dashboard'))
                        else:
                            return redirect(url_for('user_catalog'))  # Redirect to user dashboard
                    return redirect(url_for('login', error=1))  # Invalid password
        return redirect(url_for('login', error=2))  # User not found
    error_message = request.args.get('error')
    if error_message == "1":
        error_message = "Invalid password!"
    elif error_message == "2":
        error_message = "User not found!"
    else:
        error_message = None
    return render_template('login.html', error=error_message)

# Unified dashboard route
@app.route('/admin_dashboard', methods=['GET'])
def admin_dashboard():
    return render_template('admin_dashboard.html')


# Home route
@app.route('/', methods=['GET'])
def home():
    return render_template('home.html')


# Route to view the database
@app.route('/view_database', methods=['GET'])
def view_database():
    with shelve.open(DB_FILE) as db:
        users = [{
            "User ID": user_id,
            **user_data
        } for user_id, user_data in db.items()]
    return render_template('view_database.html', users=users)


# Logout route
@app.route('/logout', methods=['GET'])
def logout():
    session.clear()
    return redirect(url_for('home'))


# Profile route
@app.route('/profile', methods=['GET'])
def profile():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    user_data = get_user(user_id)
    if not user_data:
        return jsonify({'error': 'User not found'}), 404

    return render_template('profile.html', user=user_data)


@app.route('/update_my_account', methods=['GET', 'POST'])
def update_my_account():
    user_id = session.get('user_id')  # Get logged-in user's ID
    if not user_id:
        return redirect(url_for('login'))  # Redirect to "login" if not logged in

    user_data = get_user(user_id)  # Fetch user data from the database
    if not user_data:
        return jsonify({'error': 'User not found'}), 404

    if request.method == 'POST':  # Handle form submission
        data = request.form
        updates = {
            'Name': data.get('name'),
            'Email': data.get('email'),
            'Password': generate_password_hash(data.get('password')) if data.get('password') else None
        }
        updates = {key: value for key, value in updates.items() if value}  # Filter empty values

        if update_user(user_id, updates):
            flash('Account updated successfully!', 'success')
            return redirect(url_for('profile'))  # Redirect to profile page

        flash('Failed to update account!', 'danger')

    return render_template('update_my_account.html', user=user_data)  # Show the update form

@app.route('/rewards')
def rewards():
    user_id = session.get('user_id')
    user_role = session.get('role')
    user_data = None
    if user_id:
        with shelve.open(DB_FILE) as db:
            user_data = db.get(user_id)

    # If not logged in or not admin, redirect to user rewards view
    if not user_id or (user_role != 'admin' and request.path == '/rewards'):
        return redirect(url_for('user_rewards'))

    with shelve.open(REWARDS_DB) as db:
        rewards_list = [{
            "name": reward_name,
            **reward_data
        } for reward_name, reward_data in db.items()]

    return render_template('rewards.html', user=user_data, rewards=rewards_list)


@app.route('/add_reward', methods=['POST'])
def add_reward():
    reward_name = request.form.get('reward_name')
    points_required = int(request.form.get('points_required'))
    quantity = int(request.form.get('quantity'))
    image_url = request.form.get('image_url', '')

    with shelve.open(REWARDS_DB, writeback=True) as rewards_db:
        rewards_db[reward_name] = {
            'points': points_required,
            'quantity': quantity,
            'image_url': image_url
        }
        flash(f'Reward "{reward_name}" added successfully!', 'success')
    return redirect(url_for('rewards'))

@app.route('/update_image', methods=['POST'])
def update_image():
    reward_name = request.form.get('reward_name')
    new_image_url = request.form.get('new_image_url')

    with shelve.open(REWARDS_DB, writeback=True) as rewards:
        if reward_name in rewards:
            rewards[reward_name]['image_url'] = new_image_url
            flash('Image updated successfully!', 'success')
        else:
            flash('Reward not found!', 'danger')

    return redirect(url_for('rewards'))

@app.route('/update_quantity', methods=['POST'])
def update_quantity():
    reward_name = request.form.get('reward_name')
    new_quantity = int(request.form.get('new_quantity'))

    with shelve.open(REWARDS_DB, writeback=True) as rewards:
        if reward_name in rewards:
            rewards[reward_name]['quantity'] = new_quantity
            flash('Quantity updated successfully!', 'success')
        else:
            flash('Reward not found!', 'danger')

    return redirect(url_for('rewards'))

@app.route('/view_rewards', methods=['GET'])
def view_rewards():
    with shelve.open(REWARDS_DB) as db:
        rewards = [{
            "Reward Name": reward_name,
            **reward_data
        } for reward_name, reward_data in db.items()]
    return render_template('view_rewards.html', rewards=rewards)

@app.route('/remove_reward_from_cart/<reward_name>', methods=['POST'])
def remove_reward_from_cart(reward_name):
    user_id = session.get('user_id')
    if user_id:
        with shelve.open(DB_FILE, writeback=True) as db:
            user_data = db.get(user_id, None)
            if user_data:
                cart = user_data.get('Cart', [])
                cart = [item for item in cart if item['name'] != reward_name]
                user_data['Cart'] = cart
                db[user_id] = user_data
                flash(f"{reward_name} removed from your cart.", "success")
            else:
                flash("User not found.", "danger")
    else:
        flash("Please login to manage your cart.", "danger")
    return redirect(url_for('rewards'))


@app.route('/update_reward_quantity/<reward_name>', methods=['POST'])
def update_reward_quantity(reward_name):
    user_id = session.get('user_id')
    if user_id:
        with shelve.open(DB_FILE, writeback=True) as db:
            user_data = db.get(user_id, None)
            if user_data:
                new_quantity = int(request.form.get('new_quantity'))
                cart = user_data.get('Cart', [])
                for item in cart:
                    if item['name'] == reward_name:
                        item['quantity'] = new_quantity
                        break
                user_data['Cart'] = cart
                db[user_id] = user_data
                flash(f"Quantity of {reward_name} updated.", "success")
            else:
                flash("User not found.", "danger")
    else:
        flash("Please login to manage your cart.", "danger")
    return redirect(url_for('rewards'))


@app.route('/shoppingcart/<user_id>')
def shopping_cart(user_id):
    """Display the shopping cart page with books and rewards."""
    try:
        # Get user data to access cart
        with shelve.open(DB_FILE) as users_db:
            user_data = users_db.get(user_id)
            if not user_data:
                flash("User not found", "danger")
                return redirect(url_for('login'))
            
            user_cart = user_data.get('Cart', [])

        # Get books data for prices
        with shelve.open(DATABASE) as books_db:
            books = books_db.get('books', {})

        # Calculate cart total (only for books)
        cart_total = 0
        rewards = []

        # Separate books and rewards from cart
        book_cart = {}
        for item in user_cart:
            if isinstance(item, dict) and 'points' in item:
                # This is a reward
                rewards.append(item)
            elif isinstance(item, dict) and 'isbn' in item:
                # This is a book
                isbn = item['isbn']
                if isbn in books:
                    book_cart[isbn] = {
                        'title': books[isbn]['title'],
                        'price': books[isbn]['price'],
                        'quantity': item['quantity']
                    }
                    cart_total += books[isbn]['price'] * item['quantity']

        return render_template('shoppingcart.html', 
                            user_id=user_id, 
                            books=book_cart, 
                            cart=book_cart, 
                            cart_total=cart_total, 
                            rewards=rewards)
    except Exception as e:
        return f"Error: {e}", 500


@app.route('/update_cart/<user_id>', methods=['POST'])
def update_cart(user_id):
    """Update all cart item quantities at once and persist in Shelve."""
    data = request.get_json()

    try:
        with shelve.open(DATABASE_CARTS, writeback=True) as cart_db:
            user_cart = cart_db.get(user_id, {})  # Get user's cart

            # Ensure the cart exists before modifying
            if not user_cart:
                return jsonify({"success": False, "error": "Cart not found"}), 400

            # Update quantities in the user's cart
            for isbn, new_quantity in data.items():
                try:
                    new_quantity = int(new_quantity)
                except ValueError:
                    continue  # Skip invalid values

                if isbn in user_cart:
                    if new_quantity > 0:
                        user_cart[isbn]['quantity'] = new_quantity  # Update quantity
                    else:
                        del user_cart[isbn]  # Remove from cart if 0

            # Save back to the database
            cart_db[user_id] = user_cart

        session.modified = True
        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/remove_from_cart/<isbn>', methods=['POST'])
def remove_from_cart(isbn):
    """Remove a book from the user's cart."""
    user_id = session.get('user_id')
    if user_id:
        with shelve.open(DATABASE_CARTS, writeback=True) as carts_db:
            user_cart = carts_db.get(user_id, {})
            if isbn in user_cart:
                del user_cart[isbn]
                carts_db[user_id] = user_cart
                flash(f"Book removed from your cart.", "success")
            else:
                flash("Book not found in your cart.", "danger")

    return redirect(url_for('shopping_cart', user_id=user_id))


@app.route('/checkout/<user_id>', methods=['GET', 'POST'])
def checkout(user_id):
    try:
        # Fetch user data and cart
        with shelve.open(DB_FILE) as users_db:
            user_info = users_db.get(user_id)
        with shelve.open(DATABASE_CARTS) as carts_db:
            cart = carts_db.get(user_id, {})
        # Calculate the total price of items in the cart
        total_price = sum(item['price'] * item['quantity'] for item in cart.values())
        if request.method == 'POST':
            # Redirect to shipping page
            return redirect(url_for('shipping', user_id=user_id))
        # Render the checkout page with the necessary data
        return render_template('checkout.html', user_id=user_id, user_info=user_info, cart=cart, total_price=total_price)
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/shipping/<user_id>', methods=['GET', 'POST'])
def shipping(user_id):
    try:
        # Fetch user data and cart
        with shelve.open(DB_FILE) as users_db:
            user_info = users_db.get(user_id)

        with shelve.open(DATABASE_CARTS) as carts_db:
            cart = carts_db.get(user_id, {})

        # Calculate total price
        total_price = sum(item['price'] * item['quantity'] for item in cart.values())

        if request.method == 'POST':
            return redirect(url_for('payment', user_id=user_id))

        return render_template('shipping.html', user_id=user_id, user_info=user_info, cart=cart, total_price=total_price)

    except Exception as e:
        return f"Error: {e}", 500

@app.route('/payment/<user_id>', methods=['GET', 'POST'])
def payment(user_id):
    try:
        # Fetch user data and cart
        with shelve.open(DB_FILE) as users_db:
            user_info = users_db.get(user_id)

        with shelve.open(DATABASE_CARTS) as carts_db:
            cart = carts_db.get(user_id, {})

        # Calculate total price
        total_price = sum(item['price'] * item['quantity'] for item in cart.values())

        if request.method == 'POST':
            # Process payment and update stock
            with shelve.open(DATABASE, writeback=True) as books_db:
                if 'books' not in books_db:
                    flash("Inventory data is missing.", "danger")
                    return redirect(url_for('shopping_cart', user_id=user_id))

                books = books_db['books']

                # Check stock availability before processing
                for isbn, item in cart.items():
                    if isbn not in books or books[isbn].get('stock', 0) < item['quantity']:
                        flash(f"Sorry, {item['title']} is no longer available in the requested quantity.", "danger")
                        return redirect(url_for('shopping_cart', user_id=user_id))

                # Deduct stock
                for isbn, item in cart.items():
                    books[isbn]['stock'] -= item['quantity']

                books_db['books'] = books  # Save changes
                books_db.sync()  # Ensure data is written to disk

            # Update user points
            with shelve.open(DB_FILE, writeback=True) as users_db:
                user_info = users_db.get(user_id)
                if user_info:
                    user_info['Points'] = user_info.get('Points', 0) + int(total_price)
                    users_db[user_id] = user_info

            # Clear cart after successful purchase
            with shelve.open(DATABASE_CARTS, writeback=True) as carts_db:
                carts_db[user_id] = {}

            flash("Payment successful! Your order has been processed.", "success")
            return redirect(url_for('complete_order', user_id=user_id))

        return render_template('payment.html', user_id=user_id, user_info=user_info, cart=cart, total_price=total_price)

    except Exception as e:
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for('shopping_cart', user_id=user_id))

@app.route('/complete_order/<user_id>', methods=['GET'])
def complete_order(user_id):
    return render_template('CompleteOrder.html', user_id=user_id)

@app.route('/update_points', methods=['POST'])
def update_points():
    reward_name = request.form.get('reward_name')
    new_points = int(request.form.get('new_points'))

    with shelve.open(REWARDS_DB, writeback=True) as rewards:
        if reward_name in rewards:
            rewards[reward_name]['points'] = new_points
            flash('Points for reward "' + reward_name + '" updated to ' + str(new_points), 'admin-success')
        else:
            flash('Reward not found!', 'admin-danger')

    return redirect(url_for('rewards'))

@app.route('/remove_reward', methods=['POST'])
def remove_reward():
    reward_name = request.form.get('reward_name')

    with shelve.open(REWARDS_DB, writeback=True) as rewards:
        if reward_name in rewards:
            del rewards[reward_name]
            flash('Reward "' + reward_name + '" removed successfully', 'admin-success')
        else:
            flash('Reward not found!', 'danger')

    return redirect(url_for('rewards'))

@app.route('/redeem_reward', methods=['POST'])
def redeem_reward():
    if 'user_id' not in session:
        flash('Please login to redeem rewards', 'danger')
        return redirect(url_for('login'))

    user_id = session['user_id']
    reward_name = request.form.get('reward_name')

    with shelve.open(REWARDS_DB) as rewards_db:
        if reward_name not in rewards_db:
            flash('Reward not found!', 'danger')
            return redirect(url_for('rewards'))

        reward = rewards_db[reward_name]
        if reward['quantity'] <= 0:
            flash('This reward is out of stock!', 'danger')
            return redirect(url_for('rewards'))

        with shelve.open(DB_FILE) as users_db:
            user = users_db.get(user_id)
            if not user:
                flash('User not found!', 'danger')
                return redirect(url_for('rewards'))

            if user['Points'] < reward['points']:
                flash('Not enough points to redeem this reward!', 'danger')
                return redirect(url_for('rewards'))

            # Add to cart instead of directly redeeming
            cart = user.get('Cart', [])
            # Check if reward already in cart
            reward_in_cart = False
            for item in cart:
                if item.get('name') == reward_name:
                    item['quantity'] += 1
                    reward_in_cart = True
                    break

            if not reward_in_cart:
                cart.append({
                    'name': reward_name,
                    'points': reward['points'],
                    'quantity': 1
                })

            user['Cart'] = cart
            with shelve.open(DB_FILE, writeback=True) as db:
                db[user_id] = user

            flash(f'{reward_name} added to your cart!', 'success')
            return redirect(url_for('rewards'))



if __name__ == '__main__':
    initialize_databases()
    app.run(debug=True, host='0.0.0.0')
@app.route('/user_rewards')
def user_rewards():
    user_id = session.get('user_id')
    user_data = None
    if user_id:
        with shelve.open(DB_FILE) as db:
            user_data = db.get(user_id)

    with shelve.open(REWARDS_DB) as db:
        rewards_list = [{
            "name": reward_name,
            **reward_data
        } for reward_name, reward_data in db.items()]

    return render_template('rewards.html', user=user_data, rewards=rewards_list)