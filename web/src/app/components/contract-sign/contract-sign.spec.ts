import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ContractReadyEvent, ContractSignedEvent } from '../../models/events';
import { ContractSign } from './contract-sign';

/** signature_pad touches real canvas drawing APIs (fillStyle, clearRect,
 * toDataURL, ...) that jsdom doesn't implement without the native `canvas`
 * package — stub just enough of the 2D context surface for its constructor
 * and clear() to run without throwing. This is the standard way to test
 * canvas-touching components under jsdom rather than pulling in a native
 * dependency for it. */
function stubCanvas() {
  const fakeCtx = {
    fillStyle: '',
    globalCompositeOperation: '',
    scale: vi.fn(),
    clearRect: vi.fn(),
    fillRect: vi.fn(),
  };
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(fakeCtx as never);
  vi.spyOn(HTMLCanvasElement.prototype, 'toDataURL').mockReturnValue('data:image/png;base64,fake');
}

const CONTRACT: ContractReadyEvent = {
  type: 'contract_ready',
  contract_number: 'MAF-1',
  vehicle: 'Ford Mustang',
  amount_financed: '$38,500.00 USD',
  paragraphs: ['Primer párrafo del contrato.'],
  timestamp: 0,
};

describe('ContractSign', () => {
  let fixture: ComponentFixture<ContractSign>;
  let component: ContractSign;

  beforeEach(() => {
    stubCanvas();
    TestBed.configureTestingModule({ imports: [ContractSign] });
    fixture = TestBed.createComponent(ContractSign);
    fixture.componentRef.setInput('contract', CONTRACT);
    fixture.componentRef.setInput('customerName', 'Roberto Yamanaka');
    fixture.detectChanges(); // runs ngAfterViewInit, constructs the real SignaturePad
    component = fixture.componentInstance;
  });

  it('does not prefill the typed-name field with the known customer name', () => {
    expect(component.typedName()).toBe('');
  });

  describe('canSubmit', () => {
    it('is false until scrolled to the end, signed, and named', () => {
      component.scrolledToEnd.set(false);
      component.hasSignature.set(false);
      component.typedName.set('');
      expect(component.canSubmit).toBe(false);
    });

    it('is true once all three conditions are satisfied', () => {
      component.scrolledToEnd.set(true);
      component.hasSignature.set(true);
      component.typedName.set('Roberto Yamanaka');
      expect(component.canSubmit).toBe(true);
    });

    it('is false while a submission is already in flight', () => {
      component.scrolledToEnd.set(true);
      component.hasSignature.set(true);
      component.typedName.set('Roberto Yamanaka');
      component.submitting.set(true);
      expect(component.canSubmit).toBe(false);
    });

    it('rejects a name that is only whitespace', () => {
      component.scrolledToEnd.set(true);
      component.hasSignature.set(true);
      component.typedName.set('   ');
      expect(component.canSubmit).toBe(false);
    });
  });

  describe('submit', () => {
    function makeSubmittable() {
      component.scrolledToEnd.set(true);
      component.hasSignature.set(true);
      component.typedName.set('  Roberto Yamanaka  ');
    }

    it('emits the trimmed typed name and the signature data URL', () => {
      makeSubmittable();
      const emitted = vi.fn();
      component.signed.subscribe(emitted);

      component.submit();

      expect(emitted).toHaveBeenCalledWith({
        typed_name: 'Roberto Yamanaka',
        signature_image_base64: 'data:image/png;base64,fake',
      });
      expect(component.submitting()).toBe(true);
    });

    it('does nothing if canSubmit is false', () => {
      const emitted = vi.fn();
      component.signed.subscribe(emitted);

      component.submit();

      expect(emitted).not.toHaveBeenCalled();
    });
  });

  describe('markSubmitFailed', () => {
    it('resets submitting and surfaces a retry-able error', () => {
      component.submitting.set(true);

      component.markSubmitFailed('No se pudo enviar la firma.');

      expect(component.submitting()).toBe(false);
      expect(component.submitError()).toBe('No se pudo enviar la firma.');
    });
  });

  describe('signedResult', () => {
    it('switches to the read-only view once set', () => {
      const signedEvent: ContractSignedEvent = {
        type: 'contract_signed',
        contract_sent: true,
        contract_email: 'roberto@example.com',
        timestamp: 0,
      };
      fixture.componentRef.setInput('signedResult', signedEvent);
      fixture.detectChanges();

      const footer: HTMLElement = fixture.nativeElement.querySelector('.signed-footer');
      expect(footer?.textContent).toContain('Firmado por');
    });
  });
});
