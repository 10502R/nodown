// 담당: D — 팀 공통 프론트엔드 스크립트.
// 로딩 화면, 오류 안내, 선택지 강조를 여기서만 관리한다.
// 다른 팀원은 window.nodown.showLoading / showError 를 호출해서 쓰면 된다.

(function () {
  "use strict";

  var overlay = document.getElementById("loadingOverlay");
  var loadingText = document.getElementById("loadingText");
  var toast = document.getElementById("errorToast");
  var errorTitle = document.getElementById("errorTitle");
  var errorBody = document.getElementById("errorBody");
  var errorTimer = null;

  function showLoading(message) {
    if (!overlay) return;
    if (loadingText && message) loadingText.textContent = message;
    overlay.hidden = false;
  }

  function hideLoading() {
    if (overlay) overlay.hidden = true;
  }

  function showError(title, body) {
    if (!toast) return;
    if (errorTitle) errorTitle.textContent = title || "문제가 발생했습니다";
    if (errorBody) errorBody.textContent = body || "잠시 후 다시 시도해 주세요.";
    toast.hidden = false;
    window.clearTimeout(errorTimer);
    errorTimer = window.setTimeout(hideError, 8000);
  }

  function hideError() {
    if (toast) toast.hidden = true;
  }

  // data-loading 속성이 붙은 링크/폼은 자동으로 로딩 화면을 띄운다.
  document.addEventListener("click", function (event) {
    var trigger = event.target.closest("[data-loading]");
    if (trigger && trigger.tagName === "A") {
      showLoading(trigger.getAttribute("data-loading"));
    }
    if (event.target.closest("[data-error-dismiss]")) {
      hideError();
    }
  });

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (form.hasAttribute("data-loading")) {
      showLoading(form.getAttribute("data-loading"));
    }
  });

  // 뒤로가기로 돌아왔을 때 로딩 화면이 남아 있지 않게 한다.
  window.addEventListener("pageshow", hideLoading);

  // 상황 선택 라디오의 강조 표시.
  var choiceItems = document.querySelectorAll(".choice-item");
  function syncChoices() {
    choiceItems.forEach(function (item) {
      var input = item.querySelector("input[type=radio]");
      item.classList.toggle("selected", !!(input && input.checked));
    });
  }
  if (choiceItems.length) {
    choiceItems.forEach(function (item) {
      item.addEventListener("change", syncChoices);
    });
    syncChoices();
  }

  window.nodown = {
    showLoading: showLoading,
    hideLoading: hideLoading,
    showError: showError,
    hideError: hideError
  };
})();
