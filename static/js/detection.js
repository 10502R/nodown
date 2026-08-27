// 담당: A — 탐지 화면에서 사례 생성 API를 호출한다.
(function () {
  const message = document.getElementById("case-create-message");

  function showMessage(text, type) {
    if (!message) return;
    message.className = `alert alert-${type}`;
    message.textContent = text;
  }

  document.querySelectorAll(".js-create-case").forEach((button) => {
    button.addEventListener("click", async () => {
      const transactionId = button.dataset.transactionId;
      button.disabled = true;
      button.textContent = "생성 중...";

      try {
        const response = await fetch("/api/cases", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ transactionId }),
        });
        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.error || "사례 생성에 실패했습니다.");
        }

        showMessage(`${data.caseId} 사례가 생성되었습니다. 상세 화면으로 이동합니다.`, "success");
        window.location.href = data.caseUrl;
      } catch (error) {
        showMessage(error.message, "danger");
        button.disabled = false;
        button.textContent = "사례 생성";
      }
    });
  });
})();
