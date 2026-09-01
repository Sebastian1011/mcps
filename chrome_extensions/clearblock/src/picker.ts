(() => {
  const existing = document.getElementById("clearblock-picker-root");
  existing?.remove();

  const host = document.createElement("div");
  host.id = "clearblock-picker-root";
  const shadow = host.attachShadow({mode: "closed"});
  document.documentElement.append(host);

  const style = document.createElement("style");
  style.textContent = `
    :host { all: initial; }
    .outline { position: fixed; z-index: 2147483646; pointer-events: none;
      border: 3px solid #0799db; background: rgba(7,153,219,.16); box-sizing: border-box; }
    .panel { position: fixed; z-index: 2147483647; left: 50%; bottom: 24px;
      transform: translateX(-50%); min-width: 300px; max-width: calc(100vw - 40px);
      color: #202124; background: white; border: 1px solid #d4d7dc; border-radius: 10px;
      box-shadow: 0 8px 32px rgba(0,0,0,.28); padding: 14px 16px;
      font: 14px/1.4 system-ui, sans-serif; }
    .title { font-weight: 700; margin-bottom: 8px; }
    .selector { white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      color: #5f6368; font-family: ui-monospace, monospace; margin-bottom: 12px; }
    .actions { display: flex; justify-content: flex-end; gap: 8px; }
    button { border: 1px solid #c5c9ce; border-radius: 6px; background: white; padding: 7px 14px;
      font: 600 13px system-ui, sans-serif; cursor: pointer; }
    button.primary { color: white; border-color: #0799db; background: #0799db; }
  `;
  const outline = document.createElement("div");
  outline.className = "outline";
  const panel = document.createElement("div");
  panel.className = "panel";
  panel.innerHTML = `<div class="title"></div><div class="selector"></div><div class="actions">
    <button class="cancel"></button><button class="primary confirm"></button></div>`;
  shadow.append(style, outline, panel);

  const message = (key: string, fallback: string) => chrome.i18n.getMessage(key) || fallback;
  const title = panel.querySelector<HTMLElement>(".title")!;
  const selectorText = panel.querySelector<HTMLElement>(".selector")!;
  const cancelButton = panel.querySelector<HTMLButtonElement>(".cancel")!;
  const confirmButton = panel.querySelector<HTMLButtonElement>(".confirm")!;
  title.textContent = message("pickerInstruction", "Select an element to block");
  cancelButton.textContent = message("cancel", "Cancel");
  confirmButton.textContent = message("block", "Block");
  confirmButton.hidden = true;

  let hovered: Element | null = null;
  let selected: HTMLElement | null = null;
  let selector = "";
  let previewStyle: HTMLStyleElement | null = null;

  function isPickerElement(element: Element): boolean {
    return element === host || element.closest?.("#clearblock-picker-root") === host;
  }

  function updateOutline(element: Element | null): void {
    if (!element) {
      outline.hidden = true;
      return;
    }
    const rect = element.getBoundingClientRect();
    outline.hidden = false;
    Object.assign(outline.style, {
      left: `${rect.left}px`, top: `${rect.top}px`, width: `${rect.width}px`, height: `${rect.height}px`
    });
  }

  function segment(element: Element): string {
    const tag = element.localName;
    if (element.id) {
      const byId = `#${CSS.escape(element.id)}`;
      if (document.querySelectorAll(byId).length === 1) return byId;
    }
    const classes = [...element.classList]
      .filter(name => name.length < 80 && !/^(active|selected|hover|focus|open)$/i.test(name))
      .slice(0, 3)
      .map(name => `.${CSS.escape(name)}`)
      .join("");
    let value = `${tag}${classes}`;
    const parent = element.parentElement;
    if (parent && parent.querySelectorAll(`:scope > ${value}`).length > 1) {
      const siblings = [...parent.children].filter(child => child.localName === tag);
      value += `:nth-of-type(${siblings.indexOf(element) + 1})`;
    }
    return value;
  }

  function uniqueSelector(element: Element): string {
    const parts: string[] = [];
    let current: Element | null = element;
    while (current && current !== document.documentElement) {
      parts.unshift(segment(current));
      const candidate = parts.join(" > ");
      try {
        if (document.querySelectorAll(candidate).length === 1) return candidate;
      } catch {
        // Continue building a more specific selector.
      }
      current = current.parentElement;
    }
    return parts.join(" > ");
  }

  function cleanup(): void {
    previewStyle?.remove();
    document.removeEventListener("mousemove", onMouseMove, true);
    document.removeEventListener("click", onClick, true);
    document.removeEventListener("keydown", onKeyDown, true);
    window.removeEventListener("scroll", onViewportChange, true);
    window.removeEventListener("resize", onViewportChange, true);
    host.remove();
  }

  function onMouseMove(event: MouseEvent): void {
    if (selected) return;
    const target = event.target;
    if (!(target instanceof Element) || isPickerElement(target)) return;
    hovered = target;
    selectorText.textContent = uniqueSelector(target);
    updateOutline(target);
  }

  function onClick(event: MouseEvent): void {
    const path = event.composedPath();
    if (path.includes(host)) return;
    if (selected || !(event.target instanceof HTMLElement) || isPickerElement(event.target)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    selected = event.target;
    selector = uniqueSelector(selected);
    selectorText.textContent = selector;
    title.textContent = message("pickerConfirm", "Block this element?");
    confirmButton.hidden = false;
    previewStyle = document.createElement("style");
    previewStyle.textContent = `${selector} { display: none !important; }`;
    document.documentElement.append(previewStyle);
    updateOutline(null);
  }

  function onKeyDown(event: KeyboardEvent): void {
    if (event.key === "Escape") cleanup();
  }

  function onViewportChange(): void {
    if (!selected) updateOutline(hovered);
  }

  cancelButton.addEventListener("click", cleanup);
  confirmButton.addEventListener("click", async () => {
    confirmButton.disabled = true;
    const response = await chrome.runtime.sendMessage({
      type: "addElementRule",
      url: location.href,
      selector
    });
    if (!response?.ok) {
      title.textContent = response?.error || message("unknownError", "Something went wrong.");
      confirmButton.disabled = false;
      return;
    }
    previewStyle = null;
    cleanup();
  });

  document.addEventListener("mousemove", onMouseMove, true);
  document.addEventListener("click", onClick, true);
  document.addEventListener("keydown", onKeyDown, true);
  window.addEventListener("scroll", onViewportChange, true);
  window.addEventListener("resize", onViewportChange, true);
})();
