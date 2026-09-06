import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Connection } from '../../services/connection';
import { Token } from '../../services/token';
import { Intro } from './intro';

describe('Intro', () => {
  let intro: Intro;
  let tokenFetch: ReturnType<typeof vi.fn>;
  let connectionSet: ReturnType<typeof vi.fn>;
  let navigate: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    tokenFetch = vi.fn();
    connectionSet = vi.fn();
    navigate = vi.fn().mockResolvedValue(true);

    TestBed.configureTestingModule({
      providers: [
        Intro,
        { provide: Token, useValue: { fetch: tokenFetch } },
        { provide: Connection, useValue: { set: connectionSet } },
        { provide: Router, useValue: { navigateByUrl: navigate } },
      ],
    });
    intro = TestBed.inject(Intro);
  });

  describe('fieldInvalid', () => {
    it('is false for an untouched, empty field', () => {
      expect(intro.fieldInvalid('fullName')).toBe(false);
    });

    it('is true once a required field is touched and left empty', () => {
      intro.form.controls.fullName.markAsTouched();
      expect(intro.fieldInvalid('fullName')).toBe(true);
    });

    it('is false once a valid value is entered', () => {
      intro.form.controls.email.setValue('roberto@example.com');
      intro.form.controls.email.markAsTouched();
      expect(intro.fieldInvalid('email')).toBe(false);
    });
  });

  describe('startCall', () => {
    it('does nothing and marks fields touched when the form is invalid', async () => {
      await intro.startCall();
      expect(tokenFetch).not.toHaveBeenCalled();
      expect(intro.form.controls.fullName.touched).toBe(true);
    });

    it('fetches a token, stores the connection, and navigates on success', async () => {
      intro.form.setValue({ fullName: 'Roberto Yamanaka', email: 'roberto@example.com' });
      tokenFetch.mockResolvedValue({ token: 'jwt', url: 'wss://x', room: 'cierre-1' });

      await intro.startCall();

      expect(connectionSet).toHaveBeenCalledWith(
        expect.objectContaining({ token: 'jwt', customerName: 'Roberto Yamanaka' }),
      );
      expect(navigate).toHaveBeenCalledWith('/call');
      expect(intro.errorMessage()).toBeNull();
    });

    it('surfaces a friendly error message and stops submitting on failure', async () => {
      intro.form.setValue({ fullName: 'Roberto Yamanaka', email: 'roberto@example.com' });
      tokenFetch.mockRejectedValue(new Error('Agent dispatch failed'));

      await intro.startCall();

      expect(intro.errorMessage()).toBe('Agent dispatch failed');
      expect(intro.submitting()).toBe(false);
      expect(navigate).not.toHaveBeenCalled();
    });
  });
});
