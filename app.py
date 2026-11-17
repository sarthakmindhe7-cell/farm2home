
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from decimal import Decimal, InvalidOperation
from contextlib import contextmanager
import mysql.connector
from mysql.connector import IntegrityError, Error
from config import Config

app = Flask(__name__)
app.config.from_object(Config)


# =====================================================
# DATABASE CONNECTION
# =====================================================

def db():
    return mysql.connector.connect(
        host=app.config["DB_HOST"],
        user=app.config["DB_USER"],
        password=app.config["DB_PASSWORD"],
        database=app.config["DB_NAME"]
    )


@contextmanager
def get_cursor(dictionary=True):
    conn = db()
    cur = conn.cursor(dictionary=dictionary)
    try:
        yield conn, cur
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def query(sql, params=(), one=False):
    with get_cursor() as (conn, cur):
        cur.execute(sql, params)
        return cur.fetchone() if one else cur.fetchall()


def execute(sql, params=()):
    with get_cursor(dictionary=False) as (conn, cur):
        cur.execute(sql, params)
        conn.commit()
        return cur.lastrowid


# =====================================================
# VALIDATION HELPERS
# =====================================================

def valid_price(value):
    try:
        price = Decimal(str(value))
        if not price.is_finite() or price <= 0:
            return None
        return price
    except (InvalidOperation, ValueError, TypeError):
        return None


def valid_quantity(value):
    try:
        qty = int(value)
        return qty if qty >= 0 else None
    except (ValueError, TypeError):
        return None


# =====================================================
# LOGIN AND ROLE PROTECTION
# =====================================================

def login_required(role=None):
    def deco(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):

            if not session.get("user_id"):
                flash("Please log in first.", "warning")
                return redirect(url_for("login"))

            allowed = [role] if isinstance(role, str) else role

            if allowed and session.get("role") not in allowed:
                flash("Access denied.", "danger")
                return redirect(url_for("index"))

            return fn(*args, **kwargs)

        return wrapped
    return deco


@app.context_processor
def common():
    return {
        "current_user": session.get("name"),
        "role": session.get("role")
    }


# =====================================================
# HOME PAGE
# =====================================================

@app.route("/")
def index():

    term = request.args.get("q", "").strip()

    sql = """
        SELECT p.*, u.name AS farmer_name
        FROM products p
        JOIN users u ON p.farmer_id = u.user_id
        WHERE p.quantity > 0
        AND p.is_active = 1
    """

    params = []

    if term:
        sql += """
            AND (p.product_name LIKE %s
            OR p.category LIKE %s)
        """
        params.extend([f"%{term}%", f"%{term}%"])

    sql += " ORDER BY p.created_at DESC"

    products = query(sql, tuple(params))

    return render_template(
        "index.html",
        products=products,
        term=term
    )


# =====================================================
# REGISTER
# =====================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "customer")

        if not name or not email or len(password) < 6:
            flash("Enter valid details. Password must be at least 6 characters.", "danger")
            return redirect(url_for("register"))

        if role not in ("farmer", "customer"):
            flash("Invalid account type.", "danger")
            return redirect(url_for("register"))

        try:
            execute("""
                INSERT INTO users
                (name, email, phone, address, password_hash, role)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                name,
                email,
                request.form.get("phone", "").strip(),
                request.form.get("address", "").strip(),
                generate_password_hash(password),
                role
            ))

            flash("Registration successful. Please log in.", "success")
            return redirect(url_for("login"))

        except IntegrityError:
            flash("This email is already registered.", "danger")

        except Error:
            app.logger.exception("Registration database error")
            flash("Registration failed. Please try again.", "danger")

    return render_template("register.html")


# =====================================================
# LOGIN
# =====================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = query(
            "SELECT * FROM users WHERE email=%s",
            (email,),
            one=True
        )

        if user and check_password_hash(user["password_hash"], password):

            session.clear()
            session.update(
                user_id=user["user_id"],
                name=user["name"],
                role=user["role"]
            )

            flash("Welcome to Farm2Home.", "success")
            return redirect(url_for("dashboard"))

        flash("Incorrect email or password.", "danger")

    return render_template("login.html")


# =====================================================
# LOGOUT
# =====================================================

@app.route("/logout", methods=["POST"])
def logout():

    session.clear()
    flash("You have logged out.", "success")

    return redirect(url_for("index"))


# =====================================================
# DASHBOARD
# =====================================================

@app.route("/dashboard")
@login_required()
def dashboard():

    role = session["role"]

    if role == "farmer":

        products = query("""
            SELECT * FROM products
            WHERE farmer_id=%s AND is_active=1
            ORDER BY product_id DESC
        """, (session["user_id"],))

        orders = query("""
            SELECT DISTINCT o.*, u.name AS customer_name
            FROM orders o
            JOIN order_items oi ON o.order_id=oi.order_id
            JOIN products p ON oi.product_id=p.product_id
            JOIN users u ON o.customer_id=u.user_id
            WHERE p.farmer_id=%s
            ORDER BY o.order_date DESC
        """, (session["user_id"],))

        return render_template(
            "farmer_dashboard.html",
            products=products,
            orders=orders
        )

    if role == "admin":

        users = query("""
            SELECT user_id,name,email,phone,role
            FROM users ORDER BY user_id DESC
        """)

        products = query("""
            SELECT p.*,u.name AS farmer_name
            FROM products p
            JOIN users u ON p.farmer_id=u.user_id
            ORDER BY p.product_id DESC
        """)

        orders = query("""
            SELECT o.*,u.name AS customer_name
            FROM orders o
            JOIN users u ON o.customer_id=u.user_id
            ORDER BY o.order_date DESC
        """)

        return render_template(
            "admin_dashboard.html",
            users=users,
            products=products,
            orders=orders
        )

    orders = query("""
        SELECT * FROM orders
        WHERE customer_id=%s
        ORDER BY order_date DESC
    """, (session["user_id"],))

    return render_template(
        "customer_dashboard.html",
        orders=orders
    )

# =====================================================
# ADD PRODUCT
# =====================================================

@app.route("/product/add", methods=["GET", "POST"])
@login_required("farmer")
def add_product():

    if request.method == "POST":

        name = request.form.get("product_name", "").strip()
        category = request.form.get("category", "").strip()
        price = valid_price(request.form.get("price"))
        quantity = valid_quantity(request.form.get("quantity"))

        if not name or not category or price is None or quantity is None:
            flash("Please enter valid product details.", "danger")
            return redirect(url_for("add_product"))

        try:
            execute("""
                INSERT INTO products
                (farmer_id, product_name, description, category,
                price, quantity, product_image, is_active)
                VALUES (%s,%s,%s,%s,%s,%s,%s,1)
            """, (
                session["user_id"],
                name,
                request.form.get("description", "").strip(),
                category,
                price,
                quantity,
                request.form.get("product_image", "").strip()
            ))

            flash("Product added successfully.", "success")
            return redirect(url_for("dashboard"))

        except Error:
            app.logger.exception("Add product failed")
            flash("Could not add product.", "danger")

    return render_template("product_form.html", product=None)


# =====================================================
# EDIT PRODUCT
# =====================================================

@app.route("/product/<int:pid>/edit", methods=["GET", "POST"])
@login_required("farmer")
def edit_product(pid):

    product = query("""
        SELECT * FROM products
        WHERE product_id=%s AND farmer_id=%s
    """, (pid, session["user_id"]), one=True)

    if not product:
        flash("Product not found.", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        name = request.form.get("product_name", "").strip()
        category = request.form.get("category", "").strip()
        price = valid_price(request.form.get("price"))
        quantity = valid_quantity(request.form.get("quantity"))

        if not name or not category or price is None or quantity is None:
            flash("Please enter valid product details.", "danger")
            return redirect(url_for("edit_product", pid=pid))

        try:
            execute("""
                UPDATE products
                SET product_name=%s,
                    description=%s,
                    category=%s,
                    price=%s,
                    quantity=%s,
                    product_image=%s
                WHERE product_id=%s AND farmer_id=%s
            """, (
                name,
                request.form.get("description", "").strip(),
                category,
                price,
                quantity,
                request.form.get("product_image", "").strip(),
                pid,
                session["user_id"]
            ))

            flash("Product updated successfully.", "success")
            return redirect(url_for("dashboard"))

        except Error:
            app.logger.exception("Edit product failed")
            flash("Could not update product.", "danger")

    return render_template("product_form.html", product=product)


# =====================================================
# DEACTIVATE PRODUCT
# =====================================================

@app.route("/product/<int:pid>/delete", methods=["POST"])
@login_required("farmer")
def delete_product(pid):

    try:
        result = execute("""
            UPDATE products
            SET is_active=0
            WHERE product_id=%s
            AND farmer_id=%s
        """, (pid, session["user_id"]))

        flash("Product removed from customer listings.", "success")

    except Error:
        app.logger.exception("Product deactivation failed")
        flash("Could not remove product.", "danger")

    return redirect(url_for("dashboard"))


# =====================================================
# RESTORE PRODUCT
# =====================================================

@app.route("/product/<int:pid>/restore", methods=["POST"])
@login_required("farmer")
def restore_product(pid):

    try:
        execute("""
            UPDATE products
            SET is_active=1
            WHERE product_id=%s AND farmer_id=%s
        """, (pid, session["user_id"]))

        flash("Product restored successfully.", "success")

    except Error:
        app.logger.exception("Product restore failed")
        flash("Could not restore product.", "danger")

    return redirect(url_for("dashboard"))


# =====================================================
# CART ID
# =====================================================

def cart_id():

    row = query("""
        SELECT cart_id FROM carts
        WHERE customer_id=%s
    """, (session["user_id"],), one=True)

    if row:
        return row["cart_id"]

    return execute(
        "INSERT INTO carts(customer_id) VALUES(%s)",
        (session["user_id"],)
    )


# =====================================================
# VIEW CART
# =====================================================

@app.route("/cart")
@login_required("customer")
def cart():

    items = query("""
        SELECT ci.product_id,ci.quantity,
        p.product_name,p.price,p.quantity AS stock,
        (ci.quantity*p.price) AS line_total,
        p.is_active
        FROM cart_items ci
        JOIN carts c ON ci.cart_id=c.cart_id
        JOIN products p ON ci.product_id=p.product_id
        WHERE c.customer_id=%s
    """, (session["user_id"],))

    total = sum(
        (Decimal(str(i["line_total"])) for i in items),
        Decimal("0.00")
    )

    return render_template(
        "cart.html",
        items=items,
        total=total
    )


# =====================================================
# ADD TO CART
# =====================================================

@app.route("/cart/add/<int:pid>", methods=["POST"])
@login_required("customer")
def add_cart(pid):

    p = query("""
        SELECT * FROM products
        WHERE product_id=%s
        AND quantity>0
        AND is_active=1
    """, (pid,), one=True)

    if not p:
        flash("Product is not available.", "danger")
        return redirect(url_for("index"))

    cid = cart_id()

    existing = query("""
        SELECT * FROM cart_items
        WHERE cart_id=%s AND product_id=%s
    """, (cid, pid), one=True)

    if existing:

        if existing["quantity"] >= p["quantity"]:
            flash("Maximum available stock already added.", "warning")
            return redirect(url_for("cart"))

        execute("""
            UPDATE cart_items
            SET quantity=quantity+1
            WHERE cart_id=%s AND product_id=%s
        """, (cid, pid))

    else:

        execute("""
            INSERT INTO cart_items(cart_id,product_id,quantity)
            VALUES(%s,%s,1)
        """, (cid, pid))

    flash("Product added to cart.", "success")
    return redirect(url_for("cart"))


# =====================================================
# UPDATE CART
# =====================================================

@app.route("/cart/update/<int:pid>", methods=["POST"])
@login_required("customer")
def update_cart(pid):

    try:
        qty = int(request.form.get("quantity", 1))
    except ValueError:
        flash("Invalid quantity.", "danger")
        return redirect(url_for("cart"))

    cid = cart_id()

    p = query("""
        SELECT quantity,is_active FROM products
        WHERE product_id=%s
    """, (pid,), one=True)

    if qty <= 0:
        execute("""
            DELETE FROM cart_items
            WHERE cart_id=%s AND product_id=%s
        """, (cid, pid))

    elif p and p["is_active"] == 1 and qty <= p["quantity"]:

        execute("""
            UPDATE cart_items SET quantity=%s
            WHERE cart_id=%s AND product_id=%s
        """, (qty, cid, pid))

    else:
        flash("Requested quantity is not available.", "danger")

    return redirect(url_for("cart"))


# =====================================================
# CHECKOUT
# =====================================================

@app.route("/checkout", methods=["POST"])
@login_required("customer")
def checkout():

    cid = cart_id()
    address = request.form.get("address", "").strip()
    payment_mode = request.form.get("payment_mode", "Cash on Delivery")

    if not address:
        flash("Please enter delivery address.", "danger")
        return redirect(url_for("cart"))

    if payment_mode not in (
        "Cash on Delivery",
        "UPI (record only)"
    ):
        flash("Invalid payment method.", "danger")
        return redirect(url_for("cart"))

    conn = db()
    cur = conn.cursor(dictionary=True)
    try:

        cur.execute("""
            SELECT ci.product_id,ci.quantity,
            p.price,p.quantity AS stock,p.is_active
            FROM cart_items ci
            JOIN products p ON ci.product_id=p.product_id
            WHERE ci.cart_id=%s
            FOR UPDATE
        """, (cid,))

        items = cur.fetchall()

        if not items:
            flash("Your cart is empty.", "warning")
            return redirect(url_for("cart"))

        if any(
            i["is_active"] != 1 or
            i["quantity"] > i["stock"] or
            i["stock"] <= 0
            for i in items
        ):
            flash("Some products are unavailable or out of stock.", "danger")
            return redirect(url_for("cart"))

        total = sum(
            (Decimal(str(i["price"])) * i["quantity"] for i in items),
            Decimal("0.00")
        )

        cur.execute("""
            INSERT INTO orders
            (customer_id,total_amount,delivery_address,status)
            VALUES(%s,%s,%s,'Placed')
        """, (session["user_id"], total, address))

        oid = cur.lastrowid

        for item in items:

            cur.execute("""
                UPDATE products
                SET quantity=quantity-%s
                WHERE product_id=%s AND quantity >= %s
                AND is_active=1
            """, (
                item["quantity"],
                item["product_id"],
                item["quantity"]
            ))

            if cur.rowcount != 1:
                raise ValueError("Stock changed during checkout.")

            cur.execute("""
                INSERT INTO order_items
                (order_id,product_id,quantity,price)
                VALUES(%s,%s,%s,%s)
            """, (
                oid,
                item["product_id"],
                item["quantity"],
                item["price"]
            ))

        cur.execute("""
            INSERT INTO payments
            (order_id,payment_mode,amount,status)
            VALUES(%s,%s,%s,'Pending')
        """, (oid, payment_mode, total))

        cur.execute(
            "DELETE FROM cart_items WHERE cart_id=%s",
            (cid,)
        )

        conn.commit()
        flash(f"Order #{oid} placed successfully.", "success")

    except Exception:
        conn.rollback()
        app.logger.exception("Checkout failed")
        flash("Could not place order. Please try again.", "danger")

    finally:
        cur.close()
        conn.close()

    return redirect(url_for("dashboard"))


# =====================================================
# UPDATE ORDER STATUS
# =====================================================

@app.route("/order/<int:oid>/status", methods=["POST"])
@login_required(["farmer", "admin"])
def update_order_status(oid):

    status = request.form.get("status")

    allowed = [
        "Placed",
        "Accepted",
        "Processing",
        "Out for Delivery",
        "Delivered",
        "Cancelled"
    ]

    if status not in allowed:
        flash("Invalid order status.", "danger")
        return redirect(url_for("dashboard"))

    if session["role"] == "admin":

        execute("""
            UPDATE orders SET status=%s
            WHERE order_id=%s
        """, (status, oid))

    else:

        owns = query("""
            SELECT o.order_id
            FROM orders o
            JOIN order_items oi ON o.order_id=oi.order_id
            JOIN products p ON oi.product_id=p.product_id
            WHERE o.order_id=%s
            AND p.farmer_id=%s
            LIMIT 1
        """, (oid, session["user_id"]), one=True)

        if not owns:
            flash("You cannot update this order.", "danger")
            return redirect(url_for("dashboard"))

        execute("""
            UPDATE orders SET status=%s
            WHERE order_id=%s
        """, (status, oid))

    flash("Order status updated.", "success")
    return redirect(url_for("dashboard"))


# =====================================================
# PRODUCT REVIEWS
# =====================================================

@app.route("/product/<int:pid>/reviews", methods=["GET", "POST"])
def reviews(pid):

    product = query("""
        SELECT * FROM products
        WHERE product_id=%s
    """, (pid,), one=True)

    if not product:
        flash("Product not found.", "warning")
        return redirect(url_for("index"))

    if request.method == "POST":

        if session.get("role") != "customer":
            flash("Please log in as a customer.", "warning")
            return redirect(url_for("login"))

        try:
            rating = int(request.form.get("rating", 5))
        except ValueError:
            rating = 5

        if rating < 1 or rating > 5:
            rating = 5

        try:
            execute("""
                INSERT INTO reviews
                (customer_id,product_id,rating,comment)
                VALUES(%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                rating=VALUES(rating),
                comment=VALUES(comment)
            """, (
                session["user_id"],
                pid,
                rating,
                request.form.get("comment", "").strip()
            ))

            flash("Review saved successfully.", "success")

        except Error:
            app.logger.exception("Review save failed")
            flash("Could not save review.", "danger")

        return redirect(url_for("reviews", pid=pid))

    rows = query("""
        SELECT r.*,u.name AS customer_name
        FROM reviews r
        JOIN users u ON r.customer_id=u.user_id
        WHERE r.product_id=%s
        ORDER BY r.review_date DESC
    """, (pid,))

    return render_template(
        "reviews.html",
        product=product,
        reviews=rows
    )


# =====================================================
# ADMIN: CHANGE USER ROLE
# =====================================================

@app.route("/admin/user/<int:uid>/role", methods=["POST"])
@login_required("admin")
def change_role(uid):

    role = request.form.get("role")

    if role not in ("farmer", "customer", "admin"):
        flash("Invalid role.", "danger")
        return redirect(url_for("dashboard"))

    if uid == session["user_id"]:
        flash("You cannot change your own role.", "warning")
        return redirect(url_for("dashboard"))

    execute("""
        UPDATE users SET role=%s
        WHERE user_id=%s
    """, (role, uid))

    flash("User role updated successfully.", "success")
    return redirect(url_for("dashboard"))


# =====================================================
# ERROR HANDLERS
# =====================================================

@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_error(error):
    app.logger.exception("Internal server error")
    return "Something went wrong. Please try again later.", 500


# =====================================================
# APPLICATION START
# =====================================================

if __name__ == "__main__":
    app.run(debug=True)
