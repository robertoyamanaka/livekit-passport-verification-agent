import { AfterViewInit, Component, ElementRef, OnDestroy, ViewChild, input, output, signal } from '@angular/core';
import SignaturePad from 'signature_pad';
import { ContractReadyEvent, ContractSignedEvent } from '../../models/events';

/**
 * Contract review + e-signature panel. Kept as its own component (rather
 * than folded into Call) since it owns real, self-contained interaction
 * logic — scroll-to-review gating and canvas signature capture — that has
 * nothing to do with the call/transcript/photo panels around it.
 *
 * All LiveKit/Room interaction stays in the Livekit service; this component
 * only emits the captured signature and lets the parent decide what to do
 * with it, matching how the rest of the app is wired.
 */
@Component({
  selector: 'app-contract-sign',
  imports: [],
  templateUrl: './contract-sign.html',
  styleUrl: './contract-sign.css',
})
export class ContractSign implements AfterViewInit, OnDestroy {
  @ViewChild('signatureCanvas') private canvasRef!: ElementRef<HTMLCanvasElement>;
  @ViewChild('scrollArea') private scrollAreaRef!: ElementRef<HTMLElement>;

  readonly contract = input.required<ContractReadyEvent>();
  readonly customerName = input.required<string>();
  // Set once the agent confirms the signature was processed. While present,
  // the panel switches to a read-only view instead of disappearing — the
  // contract text stays visible rather than collapsing straight into a
  // one-line receipt.
  readonly signedResult = input<ContractSignedEvent | null>(null);
  readonly signed = output<{ typed_name: string; signature_image_base64: string }>();

  readonly typedName = signal('');
  readonly scrolledToEnd = signal(false);
  readonly hasSignature = signal(false);
  readonly submitting = signal(false);

  private pad: SignaturePad | null = null;

  ngAfterViewInit(): void {
    // Left blank on purpose — the customer's known name is only shown as a
    // placeholder (see the template). Requiring them to actually type their
    // full name is the point: it's the same "type your name to acknowledge"
    // step DocuSign-style flows use, not just a formality to click past.
    const canvas = this.canvasRef.nativeElement;
    // Match the canvas's backing resolution to its displayed size and the
    // device's pixel ratio, or strokes render blurry/offset — a well-known
    // signature_pad gotcha, not optional boilerplate.
    const ratio = Math.max(window.devicePixelRatio || 1, 1);
    canvas.width = canvas.offsetWidth * ratio;
    canvas.height = canvas.offsetHeight * ratio;
    canvas.getContext('2d')?.scale(ratio, ratio);

    this.pad = new SignaturePad(canvas);
    this.pad.addEventListener('endStroke', () => this.hasSignature.set(!this.pad!.isEmpty()));

    // Short contract text might already fit without scrolling — don't leave
    // the sign button permanently disabled in that case.
    const scrollEl = this.scrollAreaRef.nativeElement;
    if (scrollEl.scrollHeight <= scrollEl.clientHeight + 4) {
      this.scrolledToEnd.set(true);
    }
  }

  ngOnDestroy(): void {
    this.pad?.off();
  }

  onScroll(event: Event): void {
    const el = event.target as HTMLElement;
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 16) {
      this.scrolledToEnd.set(true);
    }
  }

  onTypedNameInput(event: Event): void {
    this.typedName.set((event.target as HTMLInputElement).value);
  }

  clearSignature(): void {
    this.pad?.clear();
    this.hasSignature.set(false);
  }

  get canSubmit(): boolean {
    return this.scrolledToEnd() && this.hasSignature() && this.typedName().trim().length > 0 && !this.submitting();
  }

  submit(): void {
    if (!this.canSubmit || !this.pad) return;
    this.submitting.set(true);
    this.signed.emit({
      typed_name: this.typedName().trim(),
      signature_image_base64: this.pad.toDataURL('image/png'),
    });
  }
}
