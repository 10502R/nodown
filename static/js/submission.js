// 할부항변 신청서(submission_form.html) 화면 전용 스크립트.
// 소비자가 서식 칸을 직접 고칠 수 있게 하고, 그 수정 내용을 sessionStorage에만
// 보관한다(서버에는 저장하지 않는다). 인쇄 버튼은 window.print()만 호출하며
// 서버 PDF 변환은 만들지 않는다.

(function () {
  "use strict";

  var sheet = document.querySelector(".sheet[data-case-id]");
  var caseId = sheet ? sheet.getAttribute("data-case-id") : "";
  var storageKey = "nd-submission-form:" + (caseId || "default");

  function loadEdits() {
    try {
      var raw = window.sessionStorage.getItem(storageKey);
      return raw ? JSON.parse(raw) : {};
    } catch (error) {
      return {};
    }
  }

  function saveEdits(edits) {
    try {
      window.sessionStorage.setItem(storageKey, JSON.stringify(edits));
    } catch (error) {
      // sessionStorage를 쓸 수 없어도 화면 입력 자체는 계속 동작해야 한다.
    }
  }

  var edits = loadEdits();

  var editableFields = document.querySelectorAll("[data-field][contenteditable='true']");
  editableFields.forEach(function (field) {
    var key = field.getAttribute("data-field");
    if (Object.prototype.hasOwnProperty.call(edits, key)) {
      field.innerHTML = edits[key];
    }

    field.addEventListener("input", function () {
      edits[key] = field.innerHTML;
      saveEdits(edits);
    });
  });

  var CHECKED = "■";
  var UNCHECKED = "□";

  var checkboxes = document.querySelectorAll("[data-checkbox]");
  checkboxes.forEach(function (box) {
    var key = "checkbox:" + box.getAttribute("data-checkbox");
    if (Object.prototype.hasOwnProperty.call(edits, key)) {
      box.textContent = edits[key] ? CHECKED : UNCHECKED;
    }

    function toggle() {
      var nowChecked = box.textContent.trim() !== CHECKED;
      box.textContent = nowChecked ? CHECKED : UNCHECKED;
      edits[key] = nowChecked;
      saveEdits(edits);
    }

    box.addEventListener("click", toggle);
    box.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggle();
      }
    });
  });

  var printButton = document.getElementById("nd-print-btn");
  if (printButton) {
    printButton.addEventListener("click", function () {
      window.print();
    });
  }
})();
