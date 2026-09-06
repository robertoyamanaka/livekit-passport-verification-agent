import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { Connection } from '../../services/connection';
import { Token } from '../../services/token';

@Component({
  selector: 'app-intro',
  imports: [ReactiveFormsModule],
  templateUrl: './intro.html',
  styleUrl: './intro.css',
})
export class Intro {
  private readonly fb = inject(FormBuilder);
  private readonly tokenService = inject(Token);
  private readonly connection = inject(Connection);
  private readonly router = inject(Router);

  readonly submitting = signal(false);
  readonly errorMessage = signal<string | null>(null);

  readonly form = this.fb.nonNullable.group({
    fullName: ['', [Validators.required, Validators.minLength(3)]],
    email: ['', [Validators.required, Validators.email]],
  });

  async startCall(): Promise<void> {
    if (this.submitting()) {
      return;
    }
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.submitting.set(true);
    this.errorMessage.set(null);

    const { fullName, email } = this.form.getRawValue();
    const room = `cierre-${crypto.randomUUID()}`;
    const identity = `cliente-${crypto.randomUUID()}`;

    try {
      const response = await this.tokenService.fetch({ identity, name: fullName, email, room });
      this.connection.set({
        token: response.token,
        url: response.url,
        room: response.room,
        customerName: fullName,
      });
      await this.router.navigateByUrl('/call');
    } catch (err) {
      this.errorMessage.set(
        err instanceof Error ? err.message : 'No se pudo iniciar la llamada. Intenta de nuevo.',
      );
      this.submitting.set(false);
    }
  }

  fieldInvalid(name: 'fullName' | 'email'): boolean {
    const control = this.form.controls[name];
    return control.invalid && control.touched;
  }
}
