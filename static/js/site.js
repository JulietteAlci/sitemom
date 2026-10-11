// Product page: reload with ?taille=N so the gold-indexed price matches the chosen size.
document.querySelectorAll("[data-price-preview]").forEach((select) => {
  select.addEventListener("change", () => {
    const url = new URL(window.location.href);
    url.searchParams.set(select.dataset.pricePreview, select.value);
    window.location.assign(url);
  });
});

// Trial kit: live counter and min/max guard (server-side validation remains authoritative).
document.querySelectorAll(".trial-form").forEach((form) => {
  const min = Number(form.dataset.min);
  const max = Number(form.dataset.max);
  const counter = form.querySelector("[data-counter]");
  const submit = form.querySelector("[data-submit]");
  // Out-of-stock dummies are rendered disabled and must stay so.
  const boxes = [...form.querySelectorAll('input[name="samples"]:not([disabled])')];

  const update = () => {
    const count = boxes.filter((box) => box.checked).length;
    counter.textContent = count;
    submit.disabled = count < min || count > max;
    boxes.forEach((box) => {
      box.disabled = !box.checked && count >= max;
    });
  };
  boxes.forEach((box) => box.addEventListener("change", update));
  update();
});

// Character counters ("Caractères utilisés : 0 / 200").
document.querySelectorAll("[data-char-count-for]").forEach((counter) => {
  const field = document.getElementById(counter.dataset.charCountFor);
  if (!field) return;
  const max = field.getAttribute("maxlength");
  const update = () => {
    counter.textContent = `Caractères utilisés : ${field.value.length} / ${max}`;
  };
  field.addEventListener("input", update);
  update();
});
