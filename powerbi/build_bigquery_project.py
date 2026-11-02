"""Create a separate BigQuery Import project without changing the CSV report."""

import argparse
import json
from pathlib import Path
import re
import shutil
import uuid


ROOT = Path(__file__).resolve().parent
NAME = "EcoBottle_AR_BigQuery"
TABLES = {
    "dim_date", "dim_channel", "dim_province", "dim_product", "dim_customer", "dim_store",
    "fact_sales_order", "fact_sales_order_item", "fact_web_session", "fact_nps_response",
}


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parameter(name, value):
    return {"name": name, "kind": "m", "expression":
            json.dumps(value) + ' meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]'}


def prepare_model(model, project, billing_project):
    """Retain the model contract, replacing only its ten Import sources."""
    tables = model["model"]["tables"]
    if {table["name"] for table in tables} != TABLES:
        raise ValueError("Expected the ten EcoBottle analytical tables")
    for table in tables:
        name = table["name"]
        source = table["partitions"][0]["source"]["expression"]
        if isinstance(source, list):
            source = "\n".join(source)
        contract = re.search(r'Table.TransformColumnTypes\(Nulos, (.*), "en-US"\)', source)
        if not contract:
            raise ValueError(f"Missing CSV type contract for {name}")
        table["partitions"] = [{"name": name, "mode": "import", "source": {
            "type": "m", "expression": f'''let
    Source = GoogleBigQuery.Database([BillingProject=BQBillingProject, Implementation="2.0"]),
    Project = Source{{[Name=BQProject]}}[Data],
    Dataset = Project{{[Name="ecobottle_analytics", Kind="Schema"]}}[Data],
    Data = Dataset{{[Name="{name}", Kind="Table"]}}[Data],
    Typed = Table.TransformColumnTypes(Data, {contract.group(1)}, "en-US")
in
    Typed'''}}]
    model["name"] = NAME
    model["model"]["expressions"] = [parameter("BQProject", project),
                                           parameter("BQBillingProject", billing_project)]
    for annotation in model["model"].get("annotations", []):
        if annotation["name"] == "PBI_QueryOrder":
            annotation["value"] = json.dumps(["BQProject", "BQBillingProject"] + [t["name"] for t in tables] + ["refresh_info"])
    measures = next(t for t in tables if t["name"] == "dim_date").setdefault("measures", [])
    measures.extend([
        {"name": "Última fecha de pedidos", "expression": "MAX(fact_sales_order[order_date])",
         "formatString": "dd/MM/yyyy HH:mm"},
        {"name": "Última fecha de actividad", "expression": "MAX(dim_date[date_value])",
         "formatString": "dd/MM/yyyy"},
    ])
    # This constant query is evaluated during refresh, not at report viewing time.
    tables.append({"name": "refresh_info", "columns": [{"name": "refreshed_at_utc",
        "dataType": "dateTime", "sourceColumn": "refreshed_at_utc", "summarizeBy": "none"}],
        "partitions": [{"name": "refresh_info", "mode": "import", "source": {"type": "m",
            "expression": 'let\n    Now = DateTimeZone.RemoveZone(DateTimeZone.FixedUtcNow())\nin\n    #table(type table [refreshed_at_utc = datetime], {{Now}})'}}],
        "measures": [{"name": "Actualización del modelo (UTC)",
            "expression": "MAX(refresh_info[refreshed_at_utc])", "formatString": "dd/MM/yyyy HH:mm"}]})
    return model


def build(output, project, billing_project=None):
    for value in (project, billing_project or project):
        if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", value):
            raise ValueError("Use a GCP project ID, not a display name or project number")
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}; choose a new output directory")
    model = prepare_model(json.loads((ROOT / "EcoBottle_AR.SemanticModel/model.bim").read_text(encoding="utf-8")),
                          project, billing_project or project)
    report_dir = output / f"{NAME}.Report"
    model_dir = output / f"{NAME}.SemanticModel"
    report_dir.mkdir(parents=True)
    model_dir.mkdir()
    shutil.copytree(ROOT / "EcoBottle_AR.Report/definition", report_dir / "definition")
    for source_dir, destination in ((ROOT / "EcoBottle_AR.Report", report_dir),
                                    (ROOT / "EcoBottle_AR.SemanticModel", model_dir)):
        platform = json.loads((source_dir / ".platform").read_text(encoding="utf-8"))
        platform["metadata"]["displayName"] = NAME
        platform["config"]["logicalId"] = str(uuid.uuid5(uuid.NAMESPACE_URL, NAME + destination.suffix))
        save(destination / ".platform", platform)
    shutil.copyfile(ROOT / "EcoBottle_AR.SemanticModel/definition.pbism", model_dir / "definition.pbism")
    save(model_dir / "model.bim", model)
    save(report_dir / "definition.pbir", {"version": "4.0", "datasetReference": {
        "byPath": {"path": f"../{NAME}.SemanticModel"}}})
    save(output / f"{NAME}.pbip", {"version": "1.0", "artifacts": [{"report": {
        "path": f"{NAME}.Report"}}], "settings": {"enableAutoRecovery": True}})
    for path in (report_dir / "definition").rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        if "Corte: 30/09/2025" in text:
            path.write_text(text.replace("Corte: 30/09/2025", "Fuente: BigQuery · Actualización automática pendiente de configurar"), encoding="utf-8")
    return output / f"{NAME}.pbip"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="GCP data project ID")
    parser.add_argument("--billing-project", help="Defaults to the data project")
    parser.add_argument("--out", type=Path, default=ROOT / ".build/bigquery")
    args = parser.parse_args()
    try:
        path = build(args.out, args.project, args.billing_project)
    except (ValueError, FileExistsError) as error:
        parser.error(str(error))
    print(f"Created {path}. Open in Desktop, authenticate, refresh and validate before publishing.")


if __name__ == "__main__":
    main()
