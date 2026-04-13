// Cold email template — clipboard copy.
document.addEventListener("DOMContentLoaded", function () {
  var copyBtn = document.getElementById("eb-copy-btn");
  var confirm = document.getElementById("eb-copy-confirm");
  var templateEl = document.getElementById("eb-template-text");
  if (!copyBtn || !templateEl) return;

  copyBtn.addEventListener("click", function () {
    var text = templateEl.textContent;

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(showCopied);
    } else {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      showCopied();
    }
  });

  function showCopied() {
    confirm.classList.add("eb__copied--visible");
    setTimeout(function () {
      confirm.classList.remove("eb__copied--visible");
    }, 2000);
  }
});
