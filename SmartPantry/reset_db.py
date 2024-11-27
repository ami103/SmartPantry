import os
from app import db, create_app
from app.models import Producto

data_cat = {
    'aceite': 1, 'aceitunas': 1, 'ajo': 4, 'alubias': 1, 'anchoas': 1, 'arroz': 1,
    'azucar': 1, 'bacon': 1, 'boquerones': 1, 'caballa': 1, 'calamar': 1, 'cazon': 1,
    'cebolla': 1, 'champinones': 1, 'chorizo': 1, 'esparragos': 1, 'garbanzos': 1,
    'harina': 1, 'huevos': 12, 'jamon': 1, 'jamon cocido': 1, 'leche': 1, 'lentejas': 1,
    'limon': 1, 'lomo': 1, 'macarrones': 1, 'maiz': 6, 'manzana': 1, 'mortadela': 1,
    'nata': 3, 'oregano': 1, 'pan': 1, 'patatas': 1, 'pepino': 1, 'pimienta': 1, 'pizza': 1,
    'platano': 1, 'pollo': 1, 'queso': 1, 'sal': 1, 'salchichas': 24, 'salchichon': 1,
    'tallarines': 1, 'ternera': 1, 'tomate': 1, 'yogur': 4, 'zanahoria': 1
}

IMAGE_DIR = os.path.join(os.path.dirname(__file__), 'app', 'static', 'images')

def reset_database():
    db.session.query(Producto).delete()

    for product, multiplicador in data_cat.items():
        image_filename = f"{product}.jpg"
        image_path = os.path.join(IMAGE_DIR, image_filename)

        if os.path.exists(image_path):
            nuevo_producto = Producto(nombre=product, cantidad=0, imagen=image_filename, multiplicador=multiplicador)
        else:
            print(f"Imagen no encontrada para el producto: {product}, se omitirá la asignación de imagen.")
            print(IMAGE_DIR)
            nuevo_producto = Producto(nombre=product, cantidad=0, multiplicador=multiplicador)

        db.session.add(nuevo_producto)
    
    db.session.commit()

    print("Base de datos reiniciada con productos de data_cat con cantidad 0, multiplicadores y las imágenes asignadas.")

if __name__ == "__main__":
    app = create_app()

    with app.app_context():
        reset_database()
