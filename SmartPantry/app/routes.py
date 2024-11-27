from flask import Blueprint, render_template, request, redirect, url_for, session, Response, jsonify
from collections import Counter
from . import db
from .models import Producto
from .utils import CONFIDENCE_THRESHOLD, DISTANCIA_UMBRAL
from ultralytics import YOLO
import ollama
import speech_recognition as sr
import pyttsx3
import cv2

main = Blueprint('main', __name__)

model = YOLO("app/models/tfg_yolo11s.pt")

productos_identificados = []

engine = pyttsx3.init()

cap = cv2.VideoCapture(0)

@main.route('/')
def index():
    return redirect(url_for('main.despensa'))

@main.route('/despensa')
def despensa():
    productos = Producto.query.order_by(Producto.cantidad.desc()).all()

    return render_template('despensa.html', productos=productos)

@main.route('/identificar')
def identificar():
    productos_contados = Counter(productos_identificados)
    return render_template('identificar.html', productos_contados=productos_contados)

def calcular_distancia(caja1, caja2):
    """Calcular la distancia euclidiana entre dos cajas delimitadoras."""
    x1, y1, w1, h1 = caja1
    x2, y2, w2, h2 = caja2
    return ((x1 - x2)**2 + (y1 - y2)**2)**0.5

def es_nueva_deteccion(caja_nueva, cajas_anteriores):
    """Determina si una nueva detección es suficientemente distinta de las anteriores."""
    for _, caja_anterior in cajas_anteriores:
        if calcular_distancia(caja_nueva, caja_anterior) < DISTANCIA_UMBRAL:
            return False
    return True

def gen_frames():
    global productos_identificados
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        results = model(frame)
        result = results[0]

        annotated_frame = result.plot()

        nuevas_detecciones = []

        for pred in result.boxes.data:
            class_id = int(pred[5])
            class_name = model.names[class_id]
            confidence = float(pred[4])
            x_min, y_min, x_max, y_max = map(int, pred[:4])

            if confidence >= CONFIDENCE_THRESHOLD:
                caja_actual = (x_min, y_min, x_max - x_min, y_max - y_min)

                if es_nueva_deteccion(caja_actual, productos_identificados):
                    nuevas_detecciones.append((class_name, caja_actual))

        if nuevas_detecciones:
            productos_identificados.extend(nuevas_detecciones)

        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@main.route('/video_feed')
def video_feed():
    """Ruta para el streaming de video desde la cámara."""
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@main.route('/get_products')
def get_products():
    productos_contados = Counter([producto for producto, _ in productos_identificados])

    return jsonify(productos_contados)

@main.route('/add_to_despensa', methods=['POST'])
def add_to_despensa():
    global productos_identificados
    productos_contados = Counter([producto for producto, _ in productos_identificados])

    for nombre_producto, cantidad in productos_contados.items():
        producto = Producto.query.filter_by(nombre=nombre_producto).first()
        if producto:
            cantidad_a_agregar = cantidad * producto.multiplicador
            producto.cantidad += cantidad_a_agregar
        else:
            nuevo_producto = Producto(nombre=nombre_producto, cantidad=cantidad, multiplicador=1.0)
            db.session.add(nuevo_producto)

    db.session.commit()

    productos_identificados.clear()

    return redirect(url_for('main.index'))

@main.route('/actualizar_cantidad/<int:producto_id>/<accion>', methods=['POST'])
def actualizar_cantidad(producto_id, accion):
    producto = Producto.query.get_or_404(producto_id)

    if accion == 'incrementar':
        producto.cantidad += 1
    elif accion == 'decrementar' and producto.cantidad > 0:
        producto.cantidad -= 1

    db.session.commit()
    return redirect(url_for('main.despensa'))

@main.route('/actualizar_cantidad_identificados/<producto_nombre>/<accion>', methods=['POST'])
def actualizar_cantidad_identificados(producto_nombre, accion):
    global productos_identificados

    for i, (nombre, caja) in enumerate(productos_identificados):
        if nombre == producto_nombre:
            if accion == 'incrementar':
                productos_identificados.append((nombre, caja))
            elif accion == 'decrementar':
                productos_identificados.pop(i)
            break

    return redirect(url_for('main.identificar'))

@main.route('/eliminar_producto_identificado/<producto_nombre>', methods=['POST'])
def eliminar_producto_identificado(producto_nombre):
    global productos_identificados

    productos_identificados = [(nombre, caja) for nombre, caja in productos_identificados if nombre != producto_nombre]

    return redirect(url_for('main.identificar'))

@main.route('/receta')
def generar_receta():
    productos = Producto.query.filter(Producto.cantidad > 0).all()
    
    if not productos:
        return render_template('receta.html', titulo="Sin Receta", ingredientes=[], instrucciones=["No tienes suficientes productos en la despensa para generar una receta."])
    
    nombres_productos = [producto.nombre for producto in productos]
    lista_ingredientes = ', '.join(nombres_productos)
    print(lista_ingredientes)
    prompt = f"""
        Genera una receta utilizando los siguientes ingredientes disponibles: {lista_ingredientes}.
        
        Intenta que sea una tortilla de patatas

        No añadas ningún comentario extra.

        Sigue estrictamente este formato:
        
        Título de la receta:
        
        Ingredientes:
         Enumera cada ingrediente de la receta.
        
        Instrucciones:
         Proporciona pasos claros y numerados para preparar la receta.
        
        Si no puedes generar una receta válida con todos los ingredientes proporcionados, crea una receta con los ingredientes disponibles de todos modos.
        """

    try:
        response = ollama.chat(
            model="llama3.1",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )
        receta_generada = response["message"]["content"]

        titulo = ""
        ingredientes = []
        instrucciones = []
        
        secciones = receta_generada.split("\n\n")

        for seccion in secciones:
            if seccion.lower().startswith("título"):
                titulo = seccion.split(":", 1)[1].strip()
            elif seccion.lower().startswith("ingredientes"):
                ingredientes = seccion.split("\n")[1:]
            elif seccion.lower().startswith("instrucciones"):
                instrucciones = seccion.split("\n")[1:]

    except Exception as e:
        titulo = "Error"
        ingredientes = []
        instrucciones = [f"Error al generar la receta: {e}"]

    return render_template('receta.html', titulo=titulo, ingredientes=ingredientes, instrucciones=instrucciones)

def speak_text(text):
    """Función para que el asistente hable."""
    engine.say(text)
    engine.runAndWait()

@main.route('/voice_command', methods=['POST'])
def voice_command():
    """Manejar los comandos de voz para navegar entre las vistas."""
    recognizer = sr.Recognizer()

    if 'audio' not in request.files:
        return {'status': 'error', 'message': 'No audio found'}, 400

    audio_file = request.files['audio']
    try:
        with sr.AudioFile(audio_file) as source:
            audio_data = recognizer.record(source)
            voice_text = recognizer.recognize_google(audio_data, language="es-ES").lower()

        if "receta" in voice_text:
            speak_text("Llevándote a la vista de recetas")
            return redirect(url_for('main.generar_receta'))

        elif "identificar" in voice_text:
            speak_text("Llevándote a la vista de identificar productos")
            return redirect(url_for('main.identificar'))

        else:
            speak_text("No entendí el comando, por favor repite")
            return {'status': 'error', 'message': 'Comando no reconocido'}, 400

    except sr.UnknownValueError:
        speak_text("No pude entender lo que dijiste, intenta de nuevo.")
        return {'status': 'error', 'message': 'Error de reconocimiento de voz'}, 400

    except sr.RequestError:
        speak_text("No pude procesar tu solicitud.")
        return {'status': 'error', 'message': 'Error de solicitud a la API de reconocimiento de voz'}, 500