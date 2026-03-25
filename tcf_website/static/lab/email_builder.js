// Email builder — live preview and clipboard copy for cold emailing a PI.
document.addEventListener("DOMContentLoaded", function () {
  var builder = document.getElementById("email-builder");
  if (!builder) return;

  var fields = builder.querySelectorAll(".eb-field");
  var copyBtn = document.getElementById("eb-copy-btn");
  var copyConfirm = document.getElementById("eb-copy-confirm");

  // Parse PI last name from full name (strip suffixes like Ph.D., Jr., III)
  var piName = builder.dataset.piName || "";
  var suffixes = ["ph.d.", "phd", "jr.", "jr", "iii", "ii", "iv", "m.d.", "md", "m.s.", "ms", "m.b.a.", "mba"];
  var nameParts = piName.split(/\s+/).filter(function (p) {
    return suffixes.indexOf(p.toLowerCase().replace(",", "")) === -1;
  });
  var piLastName = nameParts.length > 0 ? nameParts[nameParts.length - 1] : piName;

  // Update preview on every keystroke
  function updatePreview() {
    var name = document.getElementById("eb-name").value.trim();
    var year = document.getElementById("eb-year").value.trim();
    var why = document.getElementById("eb-why").value.trim();
    var experience = document.getElementById("eb-experience").value.trim();
    var availability = document.getElementById("eb-availability").value.trim();
    var hours = document.getElementById("eb-hours").value.trim();

    document.getElementById("eb-preview-subject").textContent =
      name ? "Undergraduate Research Position Inquiry — " + name : "Undergraduate Research Position Inquiry";
    document.getElementById("eb-preview-name").textContent = name || "[Your Name]";
    document.getElementById("eb-preview-year").textContent = year || "[Year & Major]";
    document.getElementById("eb-preview-why").textContent = why || "[Why you're interested — fill in above]";
    document.getElementById("eb-preview-experience").textContent = experience || "[Your experience — fill in above]";
    document.getElementById("eb-preview-availability").textContent = availability || "[Availability]";
    document.getElementById("eb-preview-signoff").textContent = name || "[Your Name]";

    // Conditionally show hours section
    var hoursSection = document.getElementById("eb-preview-hours-section");
    if (hours) {
      hoursSection.style.display = "";
      document.getElementById("eb-preview-hours").textContent = hours;
    } else {
      hoursSection.style.display = "none";
    }

    // Enable/disable copy button based on required fields
    var allFilled = true;
    fields.forEach(function (f) {
      if (f.dataset.required === "true" && !f.value.trim()) {
        allFilled = false;
      }
    });
    copyBtn.disabled = !allFilled;
  }

  fields.forEach(function (f) {
    f.addEventListener("input", updatePreview);
  });

  // Initial state
  updatePreview();

  // Copy to clipboard
  copyBtn.addEventListener("click", function () {
    var name = document.getElementById("eb-name").value.trim();
    var year = document.getElementById("eb-year").value.trim();
    var why = document.getElementById("eb-why").value.trim();
    var experience = document.getElementById("eb-experience").value.trim();
    var availability = document.getElementById("eb-availability").value.trim();
    var hours = document.getElementById("eb-hours").value.trim();

    var hoursLine = hours ? " and could commit approximately " + hours : "";

    var email =
      "Subject: Undergraduate Research Position Inquiry — " + name + "\n\n" +
      "Dear Professor " + piLastName + ",\n\n" +
      "My name is " + name + ", and I am a " + year +
      " at the University of Virginia. I am writing to inquire about potential research opportunities in your lab.\n\n" +
      why + "\n\n" +
      experience + "\n\n" +
      "I would be available starting " + availability + hoursLine +
      ". I have attached my resume for your review. Would you be available to meet briefly to discuss potential opportunities?\n\n" +
      "Thank you for your time and consideration. I completely understand if there are no openings available at this time.\n\n" +
      "Best regards,\n" +
      name + "\n" +
      "University of Virginia";

    // Clipboard API with fallback
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(email).then(showCopied);
    } else {
      // Fallback for non-HTTPS
      var textarea = document.createElement("textarea");
      textarea.value = email;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      showCopied();
    }
  });

  function showCopied() {
    copyConfirm.classList.remove("d-none");
    setTimeout(function () {
      copyConfirm.classList.add("d-none");
    }, 2000);
  }
});
