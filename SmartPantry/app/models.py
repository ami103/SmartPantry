from . import db

class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column  (db.String(80), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    imagen = db.Column(db.String(200), nullable=True)
    multiplicador = db.Column(db.Integer, default=1)   

    def __repr__(self):
        return f'<Producto {self.nombre}>'
