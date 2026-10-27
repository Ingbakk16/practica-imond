// Pegá este contenido en el Editor avanzado de una consulta en blanco llamada fnCsv.
// RutaDW es un parámetro de texto con la ruta completa a la carpeta dw/ en Windows.
(nombre as text, tipos as list) as table =>
let
    Archivo = RutaDW & Character.FromNumber(92) & nombre & ".csv",
    Origen = Csv.Document(
        File.Contents(Archivo),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars = true]),
    Nulos = Table.ReplaceValue(
        Encabezados, "", null, Replacer.ReplaceValue, Table.ColumnNames(Encabezados)
    ),
    Tipada = Table.TransformColumnTypes(Nulos, tipos, "en-US")
in
    Tipada
