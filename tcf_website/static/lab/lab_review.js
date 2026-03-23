document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".lab-vote-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var reviewId = this.dataset.reviewId;
      var action = this.dataset.action;
      var csrfToken = document.querySelector("[name=csrfmiddlewaretoken]");
      if (!csrfToken) {
        csrfToken = document.cookie
          .split("; ")
          .find(function (row) {
            return row.startsWith("csrftoken=");
          });
        csrfToken = csrfToken ? csrfToken.split("=")[1] : "";
      } else {
        csrfToken = csrfToken.value;
      }

      fetch("/lab-reviews/" + reviewId + "/" + action + "/", {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken,
          "Content-Type": "application/json",
        },
      }).then(function () {
        window.location.reload();
      });
    });
  });
});
