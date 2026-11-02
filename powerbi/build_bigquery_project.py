"""Create a separate BigQuery version of the validated EcoBottle report."""

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "bigquery"
PROJECT = "marketing-513302"
DATASET = "ecobottle_analytics"


def main():
    OUTPUT.mkdir(exist_ok=True)
    for name in ("EcoBottle_AR.Report", "EcoBottle_AR.SemanticModel"):
        shutil.copytree(
            ROOT / name,
            OUTPUT / name,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".pbi", ".platform"),
        )
    shutil.copy2(ROOT / "EcoBottle_AR.pbip", OUTPUT / "EcoBottle_AR.pbip")
    path = OUTPUT / "EcoBottle_AR.SemanticModel" / "model.bim"
    model = json.loads(path.read_text(encoding="utf-8"))
    model["model"]["expressions"] = []
    names = []
    for table in model["model"]["tables"]:
        names.append(table["name"])
        for partition in table.get("partitions", []):
            old = partition["source"]["expression"]
            typed = next(line for line in old if "Table.TransformColumnTypes" in line)
            typed = typed.replace("Table.TransformColumnTypes(Nulos,", "Table.TransformColumnTypes(Tabla,")
            partition["source"]["expression"] = [
                "let",
                f'    Origen = GoogleBigQuery.Database([BillingProject="{PROJECT}"]),',
                f'    Proyecto = Origen{{[Name="{PROJECT}"]}}[Data],',
                f'    Esquema = Proyecto{{[Name="{DATASET}", Kind="Schema"]}}[Data],',
                f'    Tabla = Esquema{{[Name="{table["name"]}", Kind="Table"]}}[Data],',
                typed,
                "in",
                "    Tipada",
            ]
    for annotation in model["model"].get("annotations", []):
        if annotation["name"] == "PBI_QueryOrder":
            annotation["value"] = json.dumps(names)
    path.write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for visual in (OUTPUT / "EcoBottle_AR.Report" / "definition").rglob("visual.json"):
        content = visual.read_text(encoding="utf-8")
        if "Corte: 30/09/2025" in content:
            visual.write_text(content.replace("Corte: 30/09/2025", "Fuente: BigQuery"), encoding="utf-8")
    assert len(names) == 10
    assert len(model["model"]["relationships"]) == 16
    assert "File.Contents" not in path.read_text(encoding="utf-8")
    print(f"Created {OUTPUT / 'EcoBottle_AR.pbip'}: 10 BigQuery tables, 16 relationships")


if __name__ == "__main__":
    main()
