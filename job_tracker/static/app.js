const deleteDialog = document.querySelector("[data-delete-dialog]");
const deleteLabel = document.querySelector("[data-delete-label]");

if (deleteDialog && deleteLabel) {
  let activeDeleteForm = null;

  document.querySelectorAll("[data-confirm-delete]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      activeDeleteForm = button.closest("form");
      deleteLabel.textContent = button.dataset.jobLabel;
      deleteDialog.returnValue = "";
      deleteDialog.showModal();
    });
  });

  deleteDialog.addEventListener("close", () => {
    if (deleteDialog.returnValue === "confirm" && activeDeleteForm) {
      activeDeleteForm.requestSubmit();
    }
    activeDeleteForm = null;
  });

  deleteDialog.querySelector("[data-close-dialog]").addEventListener("click", () => {
    deleteDialog.returnValue = "cancel";
  });
}
