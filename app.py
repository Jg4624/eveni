from flask import Flask, render_template, request, send_file, redirect, url_for
import pandas as pd
from datetime import datetime
import io
import matplotlib.pyplot as plt
import seaborn as sns
import base64

app = Flask(__name__)

def concat_nombres(df, col_primernombre, col_segundonombre, col_primerapellido, col_segundoapellido):
    return (df[col_primernombre].fillna('') + ' ' +
            df[col_segundonombre].fillna('') + ' ' +
            df[col_primerapellido].fillna('') + ' ' +
            df[col_segundoapellido].fillna('')).str.strip()

def calcular_edad(fecha_nacimiento, fecha_referencia):
    delta = fecha_referencia - fecha_nacimiento
    return delta.dt.days // 30  # Edad en meses

def clasificar_poblacion(edad_meses):
    if edad_meses < 6:
        return 'Niños lactantes'
    elif edad_meses >= 90:
        return 'Mujeres gestantes'
    elif 6 <= edad_meses < 24:
        return 'Niños/as entre 6 meses y 24 meses'
    elif 24 <= edad_meses < 36:
        return 'Niños/as entre 24 y 36 meses'
    else:
        return 'Niños/as mayores de 36 meses'

def generar_grafico(df):
    plt.figure(figsize=(12, 8))
    
    # Crear el gráfico de barras
    sns.barplot(data=df, x='Nombre_Municipio_de_la_Unidad_de_servicio', y='Total_Beneficiarios', hue='Modalidad')
    plt.xticks(rotation=90)
    plt.xlabel('Municipio')
    plt.ylabel('Cantidad de Beneficiarios')
    plt.title('Cantidad de Beneficiarios por Municipio y Modalidad')
    plt.legend(title='Modalidad')

    # Mostrar la cantidad en cada barra
    for p in plt.gca().patches:
        plt.gca().annotate(format(p.get_height(), '.0f'),
                           (p.get_x() + p.get_width() / 2., p.get_height()),
                           ha = 'center', va = 'center',
                           xytext = (0, 9), textcoords = 'offset points')

    plt.tight_layout()

    # Guardar el gráfico en un objeto BytesIO
    output_img = io.BytesIO()
    plt.savefig(output_img, format='png')
    output_img.seek(0)
    plt.close()

    # Convertir la imagen a base64
    img_base64 = base64.b64encode(output_img.getvalue()).decode('utf-8')
    return img_base64

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files['file']
        if file:
            global data_for_plot
            vinculados = pd.read_csv(file)

            # Convertir la fecha de nacimiento a datetime
            vinculados['Fecha_de_nacimiento_del_beneficiario'] = pd.to_datetime(vinculados['Fecha_de_nacimiento_del_beneficiario'], dayfirst=True)

            # Recoger la fecha de referencia del formulario
            fecha_referencia = request.form['fecha_referencia']
            fecha_referencia = datetime.strptime(fecha_referencia, "%d/%m/%Y")

            # Calcular la edad en meses
            vinculados['Edad_en_meses'] = calcular_edad(vinculados['Fecha_de_nacimiento_del_beneficiario'], fecha_referencia)

            # Concatenar nombres completos
            vinculados['NombreCompleto'] = concat_nombres(vinculados, 
                                                          'Primer_Nombre_del_beneficiario', 
                                                          'Segundo_Nombre_del_beneficiario', 
                                                          'Primer_apellido_del_beneficiario', 
                                                          'Segundo_apellido_del_beneficiario')

            # Clasificar población según la edad en meses
            vinculados['Categoria'] = vinculados['Edad_en_meses'].apply(clasificar_poblacion)

            # Consolidado por Municipio y Modalidad
            global data_for_plot
            data_for_plot = vinculados.groupby(['Nombre_Municipio_de_la_Unidad_de_servicio', 'Modalidad']).agg({'NombreCompleto': pd.Series.nunique}).reset_index()
            data_for_plot = data_for_plot.rename(columns={'NombreCompleto': 'Total_Beneficiarios'})

            # Generar gráfico en base64
            global img_base64
            img_base64 = generar_grafico(data_for_plot)

            # Guardar los resultados en un archivo Excel en memoria
            output_excel = io.BytesIO()
            with pd.ExcelWriter(output_excel, engine='xlsxwriter') as writer:
                vinculados.groupby(['Nombre_Municipio_de_la_Unidad_de_servicio', 'Modalidad', 'Categoria']).agg({'NombreCompleto': pd.Series.nunique}).reset_index().rename(columns={'NombreCompleto': 'Cantidad_Beneficiarios'}).to_excel(writer, sheet_name='Consolidado', index=False)
                data_for_plot.to_excel(writer, sheet_name='Total_Vinculados', index=False)

            output_excel.seek(0)
            global excel_file
            excel_file = output_excel.read()
            return redirect(url_for('index'))

    return render_template('index.html', img_base64=img_base64 if 'img_base64' in globals() else None)

@app.route('/descargar_excel')
def descargar_excel():
    if 'excel_file' not in globals():
        return redirect(url_for('index'))
    
    return send_file(io.BytesIO(excel_file), mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='reporte_vinculados.xlsx')

if __name__ == '__main__':
    app.run(debug=True)
