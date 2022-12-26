import { Component, Inject } from '@angular/core';
import { MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';

export interface ConfirmationDialogData {
    title: string;
}

@Component({
    selector: 'dialog-confirmation-dialog',
    template: `
    <app-dialog>
            <div class="py-3">
                <div>
                    <h2>{{data.title}}</h2>

                    <div class="d-flex justify-content-center">
                        <span class="me-5 ms-2">
                            <button mat-stroked-button (click)="exit(false)">Cancel</button>
                        </span>
                        <span class="ms-5 me-2">
                            <button mat-stroked-button color="primary" (click)="exit(true)">Confirm</button>
                        </span>
                    </div>
                </div>
            </div>
    </app-dialog>
    `
})
export class ConfirmationDialog {
    constructor(
        public dialogRef: MatDialogRef<ConfirmationDialog>,
        @Inject(MAT_DIALOG_DATA) public data: ConfirmationDialogData
    ) { }

    public exit(result: boolean = false): void {
        this.dialogRef.close(result);
    }
}
