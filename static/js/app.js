const page = document.body.dataset.page;
const header = document.querySelector("#site-header");
const footer = document.querySelector("#site-footer");
const links = [["home", "/", "Home"], ["about", "/about", "About"], ["classes", "/classes", "Classes"], ["blog", "/blog", "Journal"], ["contact", "/contact", "Contact"]];
header.innerHTML = `<header class="site-header"><a class="logo" href="/">still<i>.</i></a><button class="menu-button" aria-label="Open menu" aria-expanded="false">☰</button><nav class="nav">${links.map(([key, href, label]) => `<a class="${page === key ? "active" : ""}" href="${href}">${label}</a>`).join("")}<a class="nav-cta" href="/classes">Book a class</a></nav></header>`;
footer.innerHTML = `<footer class="site-footer"><a class="logo" href="/">still<i>.</i></a><div><p>Mindful movement.<br>Meaningful connection.</p></div><div><p>1428 SE Division Street<br>Portland, OR 97202</p></div><div><a href="mailto:hello@stillstudio.com">hello@stillstudio.com</a><br><a href="tel:+15035550142">(503) 555-0142</a></div><small>© ${new Date().getFullYear()} Still Studio</small></footer>`;
const menuButton = document.querySelector(".menu-button");
menuButton.addEventListener("click", () => {
  const open = document.querySelector(".nav").classList.toggle("open");
  menuButton.setAttribute("aria-expanded", String(open));
});
const observer = new IntersectionObserver(entries => entries.forEach(entry => {
  if (entry.isIntersecting) entry.target.classList.add("visible");
}), { threshold: .12 });
document.querySelectorAll(".reveal").forEach(element => observer.observe(element));
document.querySelectorAll(".article-toggle").forEach(button => button.addEventListener("click", () => {
  const article = button.nextElementSibling;
  const open = article.classList.toggle("open");
  button.textContent = open ? "Close article ↑" : "Read article →";
  button.setAttribute("aria-expanded", String(open));
}));
const newsletter = document.querySelector("#newsletter-form");
if (newsletter) newsletter.addEventListener("submit", event => {
  event.preventDefault();
  newsletter.querySelector(".form-message").textContent = "Thank you. A little stillness is on its way.";
  newsletter.reset();
});
const contact = document.querySelector("#contact-form");
if (contact) contact.addEventListener("submit", event => {
  event.preventDefault();
  contact.querySelector(".form-message").textContent = "Thank you. We will be in touch within two studio days.";
  contact.reset();
});
const paymentMessage = document.querySelector("#payment-message");
const paymentParams = new URLSearchParams(location.search);
if (paymentParams.has("success") && paymentMessage) paymentMessage.textContent = "Thank you. Your class reservation payment was received.";
if (paymentParams.has("cancelled") && paymentMessage) paymentMessage.textContent = "Checkout was cancelled. Your place has not been reserved.";
document.querySelectorAll(".checkout").forEach(button => button.addEventListener("click", async () => {
  const original = button.innerHTML;
  button.disabled = true;
  button.textContent = "Opening checkout…";
  if (paymentMessage) paymentMessage.textContent = "";
  try {
    const response = await fetch("/api/checkout", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ plan: button.dataset.plan }) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Checkout is unavailable.");
    location.href = data.url;
  } catch (error) {
    if (paymentMessage) paymentMessage.textContent = error.message;
    button.disabled = false;
    button.innerHTML = original;
  }
}));
