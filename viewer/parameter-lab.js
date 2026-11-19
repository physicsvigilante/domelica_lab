"use strict";
(() => {
  const inputs = document.getElementById("inputs");
  const status = document.getElementById("status");
  const form = document.getElementById("controls");
  const button = document.getElementById("run");
  const frame = document.getElementById("result");
  const download = document.getElementById("download");
  const placeholder = document.getElementById("viewer-placeholder");
  let definitions = null;
  const fields = new Map();

  function setStatus(message, error = false) {
    status.textContent = message;
    status.style.color = error ? "#ffb2a0" : "#aac1d0";
  }
  function labelFor(key) {
    return ({ cartMass: "Cart mass", bobMass: "Pendulum mass", springStiffness: "Spring stiffness", initialAngle: "Release angle" })[key] || key;
  }
  async function load() {
    button.disabled = true;
    try {
      const response = await fetch("/api/config", { cache: "no-store" });
      if (!response.ok) throw new Error("Could not load runtime parameters");
      const config = await response.json();
      definitions = config.parameters;
      for (const [key, definition] of Object.entries(definitions)) {
        const degrees = definition.unit === "rad";
        const block = document.createElement("div"); block.className = "field";
        const label = document.createElement("label"); label.htmlFor = "param-" + key;
        label.textContent = labelFor(key) + " (" + (degrees ? "degrees" : definition.unit) + ")";
        const input = document.createElement("input");
        input.id = label.htmlFor; input.type = "number"; input.step = "any"; input.required = true;
        input.value = String(degrees ? definition.default * 180 / Math.PI : definition.default);
        if (Object.hasOwn(definition, "minimumExclusive")) input.min = String(degrees ? definition.minimumExclusive * 180 / Math.PI : definition.minimumExclusive);
        if (Object.hasOwn(definition, "maximumExclusive")) input.max = String(degrees ? definition.maximumExclusive * 180 / Math.PI : definition.maximumExclusive);
        block.append(label, input); inputs.append(block); fields.set(key, { input, degrees });
      }
      button.disabled = false;
      setStatus("Ready. The four inputs are applied before initialization of a new native solve.");
    } catch (error) { setStatus(error.message, true); }
  }
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!definitions || !form.reportValidity()) return;
    const parameters = {};
    for (const [key, { input, degrees }] of fields) {
      const value = input.valueAsNumber;
      if (!Number.isFinite(value) || (Object.hasOwn(definitions[key], "minimumExclusive") &&
          value <= (degrees ? definitions[key].minimumExclusive * 180 / Math.PI : definitions[key].minimumExclusive)) ||
          (Object.hasOwn(definitions[key], "maximumExclusive") &&
          value >= (degrees ? definitions[key].maximumExclusive * 180 / Math.PI : definitions[key].maximumExclusive))) {
        setStatus("Enter valid numbers within the physical parameter limits.", true); return;
      }
      parameters[key] = degrees ? value * Math.PI / 180 : value;
    }
    button.disabled = true;
    setStatus("Calculating fresh native motion and preparing the viewer…");
    try {
      const response = await fetch("/api/run", {
        method: "POST", cache: "no-store",
        headers: { "Content-Type": "application/json", "X-Domelica-Request": "1" },
        body: JSON.stringify({ parameters })
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "The native simulation failed");
      frame.src = result.url; frame.hidden = false; placeholder.hidden = true;
      download.href = result.url; download.classList.add("visible");
      setStatus("Fresh native result: " + result.samples + " samples, " + result.simulatedSeconds + " simulated seconds; 0 runtime compiler calls.");
    } catch (error) { setStatus(error.message, true); }
    finally { button.disabled = false; }
  });
  load();
})();
