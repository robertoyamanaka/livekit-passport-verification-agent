import { AfterViewInit, Component, ElementRef, OnDestroy, OnInit, ViewChild, inject } from '@angular/core';
import { Router } from '@angular/router';
import { ContractSign } from '../../components/contract-sign/contract-sign';
import { Connection, PendingConnection } from '../../services/connection';
import { Livekit } from '../../services/livekit';

@Component({
  selector: 'app-call',
  imports: [ContractSign],
  templateUrl: './call.html',
  styleUrl: './call.css',
})
export class Call implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('localVideo') private videoRef!: ElementRef<HTMLVideoElement>;

  private readonly connectionStore = inject(Connection);
  private readonly router = inject(Router);
  readonly livekit = inject(Livekit);

  customerName = '';
  private pending: PendingConnection | null = null;

  ngOnInit(): void {
    this.pending = this.connectionStore.consume();
    if (!this.pending) {
      // No token in hand (e.g. a page reload) — the flow always starts at /.
      this.router.navigateByUrl('/');
      return;
    }
    this.customerName = this.pending.customerName;
  }

  ngAfterViewInit(): void {
    if (!this.pending) {
      return;
    }
    this.livekit
      .connect(this.pending.url, this.pending.token, this.videoRef.nativeElement)
      .catch((err) => console.error('Failed to connect to LiveKit room', err));
  }

  ngOnDestroy(): void {
    this.livekit.disconnect();
  }

  enableAudio(): void {
    this.livekit.retryAudio().catch((err) => console.error('Failed to enable audio', err));
  }

  onContractSigned(payload: { typed_name: string; signature_image_base64: string }): void {
    this.livekit.submitSignature(payload).catch((err) => console.error('Failed to submit signature', err));
  }

  get presenceLabel(): string {
    switch (this.livekit.presence()) {
      case 'connecting':
        return 'Conectando…';
      case 'waiting_for_agent':
        return 'Conectando con el agente…';
      case 'agent_connected':
        return 'Agente conectado';
      case 'disconnected':
        return 'Llamada finalizada';
      case 'error':
        return 'Error de conexión';
    }
  }
}
