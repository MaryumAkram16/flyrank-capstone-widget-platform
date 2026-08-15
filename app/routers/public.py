from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories import widgets_repo
from app.schemas import WidgetConfigOut

router = APIRouter(tags=["public"])

# Kept as a plain string bundle for the capstone — a real build step
# (esbuild/rollup) would generate this; see the brief's stretch goals.
_WIDGET_JS = """
(function () {
  var script = document.currentScript;
  var id = new URL(script.src).searchParams.get("id");
  if (!id) return;

  var apiBase = new URL(script.src).origin;

  fetch(apiBase + "/widgets/" + id + "/config")
    .then(function (r) { return r.json(); })
    .then(function (cfg) { renderWidget(cfg); })
    .catch(function () { /* config fetch failed — fail silently, no widget shown */ });

  function renderWidget(cfg) {
    var container = document.createElement("div");
    container.className = "fr-widget fr-widget-" + cfg.type;

    var title = document.createElement("h3");
    title.textContent = cfg.title;
    container.appendChild(title);

    if (cfg.description) {
      var desc = document.createElement("p");
      desc.textContent = cfg.description;
      container.appendChild(desc);
    }

    var form = document.createElement("form");

    cfg.fields.forEach(function (f) {
      var label = document.createElement("label");
      label.textContent = f.label;
      var input = f.type === "textarea" ? document.createElement("textarea")
                : document.createElement("input");
      if (f.type !== "textarea") input.type = f.type === "checkbox" ? "checkbox" : "text";
      input.name = f.name;
      if (f.required) input.required = true;
      label.appendChild(input);
      form.appendChild(label);
    });

    // Honeypot — hidden via CSS, never shown to a real visitor.
    var honeypot = document.createElement("input");
    honeypot.type = "text";
    honeypot.name = "website";
    honeypot.style.cssText = "position:absolute;left:-9999px;";
    honeypot.tabIndex = -1;
    honeypot.autocomplete = "off";
    form.appendChild(honeypot);

    var button = document.createElement("button");
    button.type = "submit";
    button.textContent = cfg.button_text;
    form.appendChild(button);

    var status = document.createElement("p");
    status.className = "fr-widget-status";

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var data = {};
      cfg.fields.forEach(function (f) {
        var el = form.elements[f.name];
        data[f.name] = f.type === "checkbox" ? String(el.checked) : el.value;
      });
      fetch(apiBase + "/submissions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          widget_id: id,
          data: data,
          website: form.elements["website"].value,
        }),
      })
        .then(function (r) {
          status.textContent = r.ok ? "Thanks!" : "Something went wrong.";
        })
        .catch(function () {
          status.textContent = "Something went wrong.";
        });
    });

    container.appendChild(form);
    container.appendChild(status);
    document.body.appendChild(container);
  }
})();
"""


@router.get("/widget.js")
def get_widget_bundle():
    return Response(
        content=_WIDGET_JS,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.get("/widgets/{widget_id}/config", response_model=WidgetConfigOut)
def get_widget_config(widget_id: str, response: Response, db: Session = Depends(get_db)):
    widget = widgets_repo.get_public(db, widget_id)
    if widget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")
    response.headers["Cache-Control"] = "public, max-age=60"
    response.headers["Access-Control-Allow-Origin"] = "*"
    return widget
