import { Routes } from '@angular/router';
import { Call } from './pages/call/call';
import { Intro } from './pages/intro/intro';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'intro' },
  { path: 'intro', component: Intro },
  { path: 'call', component: Call },
  { path: '**', redirectTo: 'intro' },
];
