from flask import Flask, render_template, request, redirect, url_for, flash
from flask_wtf.csrf import CSRFProtect
from flask import g
import os

from config import DevelopmentConfig
from models import db, DetallePizza, Pedido, User
import forms
from io import open
from flask_login import login_required
# IMPORTS para Flask-Login
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

app = Flask(__name__)
app.config.from_object(DevelopmentConfig)
csrf = CSRFProtect(app)

# Configura el login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Nombre de la ruta para login


ARCHIVO_TEMP = "pizzas_temp.txt"

@login_manager.user_loader
def load_user(user_id):
    """
    Función obligatoria para Flask-Login.
    Recibe el ID (string) y debe retornar el usuario o None.
    """
    return User.query.get(int(user_id))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.route("/")
def home():
    return redirect(url_for('login'))



@app.route("/index", methods=["GET", "POST"])
@login_required
def index():
    """
    Muestra el formulario principal (datos del cliente + selección de pizzas).
    Al enviar el form con una pizza, la "agrega" a un archivo de texto temporal.
    """
    form_pizza = forms.PizzaForm(request.form)

    if request.method == "POST":
        # Se presionó el botón "Agregar"
        if form_pizza.validate():
            # 1) Tomamos datos del formulario (tamaño, ingredientes, cantidad)
            tamano = form_pizza.tamano.data   # "Chica", "Mediana", "Grande"
            # ingredientes es una lista de strings ,
            #  Ajusta según el forms.py
            ingredientes_list = form_pizza.ingredientes.data  
            cantidad = form_pizza.cantidad.data
            # calculamos el precio base
            precio_base = 0
            if tamano == "Chica":
                precio_base = 40
            elif tamano == "Mediana":
                precio_base = 80
            elif tamano == "Grande":
                precio_base = 120
            elif tamano == "Familiar":
                precio_base = 150
            elif tamano == "Jumbo":
                precio_base = 200

            # Cada ingrediente extra cuesta 10
            precio_ingredientes = len(ingredientes_list) * 10
            subtotal = (precio_base + precio_ingredientes) * cantidad

            # 2) Guardamos estos datos en un archivo temporal
            # Formato: tamano|ingredientes_concatenados|cantidad|subtotal
            ingredientes_str = ", ".join(ingredientes_list)
            linea = f"{tamano}|{ingredientes_str}|{cantidad}|{subtotal}\n"

            with open(ARCHIVO_TEMP, "a", encoding="utf-8") as f:
                f.write(linea)

            flash("Pizza agregada al pedido.", "success")
        else:
            flash("Error en datos de la pizza.", "danger")

    # Leemos del archivo temporal para mostrar en la tabla la lista de pizzas
    pizzas_temp = []
    if os.path.exists(ARCHIVO_TEMP):
        with open(ARCHIVO_TEMP, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("|")
                if len(parts) == 4:
                    pizzas_temp.append({
                        "tamano": parts[0],
                        "ingredientes": parts[1],
                        "cantidad": parts[2],
                        "subtotal": parts[3]
                    })

    return render_template("index.html", form=form_pizza, pizzas=pizzas_temp)

@app.route("/quitar", methods=["POST"])
def quitar():
    """
    Elimina UNA pizza del archivo temporal. 
    Supongamos que recibimos un índice (u otra referencia) para saber qué línea quitar.
    """
    idx = request.form.get("idx")  # índice de la pizza a quitar
    if idx is not None and os.path.exists(ARCHIVO_TEMP):
        idx = int(idx)
        # Leemos todas las líneas
        with open(ARCHIVO_TEMP, "r", encoding="utf-8") as f:
            lines = f.readlines()
        # Reescribimos todas MENOS la de la posición idx
        with open(ARCHIVO_TEMP, "w", encoding="utf-8") as f:
            for i, line in enumerate(lines):
                if i != idx:
                    f.write(line)
        flash("Pizza eliminada del pedido.", "warning")

    return redirect(url_for("index"))

@app.route("/terminar", methods=["POST"])
def terminar():
    """
    Al dar clic en 'Terminar':
      1) Lee las pizzas del archivo temporal
      2) Calcula el total
      3) Inserta un registro en la tabla 'pedidos' + 'detalle_pizzas'
      4) Limpia el archivo temporal
      5) Muestra flash con el total final
    """
    form_pizza = forms.PizzaForm(request.form)

    # Tomar también los datos del cliente (nombre, dirección, teléfono, fecha)
    nombre = request.form.get("nombre")
    direccion = request.form.get("direccion")
    telefono = request.form.get("telefono")
    fecha_pedido = request.form.get("fecha_pedido")

    pizzas_temp = []
    total_general = 0.0

    if os.path.exists(ARCHIVO_TEMP):
        with open(ARCHIVO_TEMP, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("|")
                if len(parts) == 4:
                    tamano = parts[0]
                    ingredientes = parts[1]
                    cantidad = int(parts[2])
                    subtotal = float(parts[3])
                    pizzas_temp.append((tamano, ingredientes, cantidad, subtotal))
                    total_general += subtotal

  
    # Si no hay pizzas en pizzas_temp, no se debe crear el pedido
    if not pizzas_temp:
        flash("No hay pizzas agregadas. Agrega al menos una pizza antes de terminar.", "danger")
        return redirect(url_for("index"))

    # 1) Creamos un objeto Pedido
    nuevo_pedido = Pedido(
        nombre=nombre,
        direccion=direccion,
        telefono=telefono
        
    )
    nuevo_pedido.total = total_general
    db.session.add(nuevo_pedido)
    db.session.commit()

    # 2) Insertamos los DetallePizza asociados
    for (tamano, ingredientes, cantidad, subtotal) in pizzas_temp:
        detalle = DetallePizza(
            pedido_id=nuevo_pedido.id,
            tamano=tamano,
            ingredientes=ingredientes,
            cantidad=cantidad,
            subtotal=subtotal
        )
        db.session.add(detalle)

    db.session.commit()

    # 3) Borramos el archivo temporal
    if os.path.exists(ARCHIVO_TEMP):
        os.remove(ARCHIVO_TEMP)

    # 4) Mensaje flash con el total
    flash(f"Pedido finalizado. Total a pagar: ${total_general:.2f}", "success")

    return redirect(url_for("index"))

    """
    Al dar clic en 'Terminar':
      1) Lee las pizzas del archivo temporal
      2) Calcula el total
      3) Inserta un registro en la tabla 'pedidos' + 'detalle_pizzas'
      4) Limpia el archivo temporal
      5) Muestra flash con el total final
    """
    form_pizza = forms.PizzaForm(request.form)

    # Tomar también los datos del cliente (nombre, dirección, teléfono, fecha)
    nombre = request.form.get("nombre")
    direccion = request.form.get("direccion")
    telefono = request.form.get("telefono")
    fecha_pedido = request.form.get("fecha_pedido")

    pizzas_temp = []
    total_general = 0.0

    if os.path.exists(ARCHIVO_TEMP):
        with open(ARCHIVO_TEMP, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("|")
                if len(parts) == 4:
                    tamano = parts[0]
                    ingredientes = parts[1]
                    cantidad = int(parts[2])
                    subtotal = float(parts[3])
                    pizzas_temp.append((tamano, ingredientes, cantidad, subtotal))
                    total_general += subtotal

    # 1) Creamos un objeto Pedido
    nuevo_pedido = Pedido(
        nombre=nombre,
        direccion=direccion,
        telefono=telefono
        
    )
    nuevo_pedido.total = total_general
    db.session.add(nuevo_pedido)
    db.session.commit()

    # 2) Insertamos los DetallePizza asociados
    for (tamano, ingredientes, cantidad, subtotal) in pizzas_temp:
        detalle = DetallePizza(
            pedido_id=nuevo_pedido.id,
            tamano=tamano,
            ingredientes=ingredientes,
            cantidad=cantidad,
            subtotal=subtotal
        )
        db.session.add(detalle)

    db.session.commit()

    # 3) Borramos el archivo temporal
    if os.path.exists(ARCHIVO_TEMP):
        os.remove(ARCHIVO_TEMP)

    # 4) Mensaje flash con el total
    flash(f"Pedido finalizado. Total a pagar: ${total_general:.2f}", "success")

    return redirect(url_for("index"))


# ---------------------------
# filtrar ventas por día o mes
# ---------------------------
@app.route("/ventas", methods=["GET", "POST"])
def ventas():
    """
    Muestra ventas del día o del mes, dependiendo de la selección del usuario.
    """
    # 
    filtro = request.form.get("filtro_fecha")  # "dia" o "mes"
    fecha = request.form.get("fecha")  # Input type="date"

    pedidos_filtrados = []
    total_ventas = 0.0

    if request.method == "POST" and fecha:
        # Convertimos la fecha (yyyy-mm-dd) en un datetime
        import datetime
        fecha_obj = datetime.datetime.strptime(fecha, "%Y-%m-%d")

        if filtro == "dia":
            # Filtrar por año, mes y día
            pedidos_filtrados = Pedido.query.filter(
                db.extract('year', Pedido.fecha_pedido) == fecha_obj.year,
                db.extract('month', Pedido.fecha_pedido) == fecha_obj.month,
                db.extract('day', Pedido.fecha_pedido) == fecha_obj.day
            ).all()
        elif filtro == "mes":
            # Filtrar por año y mes
            pedidos_filtrados = Pedido.query.filter(
                db.extract('year', Pedido.fecha_pedido) == fecha_obj.year,
                db.extract('month', Pedido.fecha_pedido) == fecha_obj.month
            ).all()

    # Calculamos totales
    total_ventas = sum([p.total for p in pedidos_filtrados])

    return render_template("ventas.html",
                           pedidos=pedidos_filtrados,
                           total_ventas=total_ventas)
	
@app.route("/historial", methods=["GET", "POST"])
@login_required
def historial():
    """
    Muestra un formulario para filtrar las ventas (pedidos) por día o por mes,
    y despliega los resultados en una tabla.
    """
    filtro = request.form.get("filtro_fecha")  # "dia" o "mes"
    fecha = request.form.get("fecha")          # Input type="date"

    pedidos_filtrados = []
    total_ventas = 0.0

    if request.method == "POST" and fecha:
        import datetime
        fecha_obj = datetime.datetime.strptime(fecha, "%Y-%m-%d")

        if filtro == "dia":
            # Filtrar por año, mes y día
            pedidos_filtrados = Pedido.query.filter(
                db.extract('year', Pedido.fecha_pedido) == fecha_obj.year,
                db.extract('month', Pedido.fecha_pedido) == fecha_obj.month,
                db.extract('day', Pedido.fecha_pedido) == fecha_obj.day
            ).all()
        elif filtro == "mes":
            # Filtrar por año y mes
            pedidos_filtrados = Pedido.query.filter(
                db.extract('year', Pedido.fecha_pedido) == fecha_obj.year,
                db.extract('month', Pedido.fecha_pedido) == fecha_obj.month
            ).all()

    # Calculamos el total de las ventas filtradas
    total_ventas = sum([p.total for p in pedidos_filtrados])

    return render_template(
        "historial.html", 
        pedidos=pedidos_filtrados, 
        total_ventas=total_ventas
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Vista para iniciar sesión.
    Si se autentica correctamente, se redirige a 'index'.
    """
    form_login = forms.LoginForm()
    if request.method == 'POST':
        if form_login.validate_on_submit():
            # Obtiene datos del formulario
            username = form_login.username.data
            password = form_login.password.data

            # Busca en DB (ajusta a tu lógica real)
            user = User.query.filter_by(username=username).first()
            if user and user.password == password:
                # Autenticación exitosa
                login_user(user)
                flash('Sesión iniciada correctamente', 'success')
                return redirect(url_for('index'))
            else:
                flash('Usuario o contraseña inválidos', 'danger')
                return redirect(url_for('login'))
    return render_template('login.html', form=form_login)

@app.route('/logout')
def logout():
    """
    Cierra la sesión actual y redirige al login.
    """
    logout_user()
    flash('Sesión cerrada.', 'info')
    return redirect(url_for('login'))



if __name__ == '__main__':
	csrf.init_app(app)
	db.init_app(app)

	with app.app_context():
		db.create_all()
	app.run()