// Simple client-side router for navigation
export class Router {
  private listeners: Set<(path: string) => void> = new Set();
  private currentPath: string = '/';

  constructor() {
    // Initialize with current path
    this.currentPath = this.getPathFromUrl();
    
    // Listen for browser navigation
    window.addEventListener('popstate', () => {
      this.currentPath = this.getPathFromUrl();
      this.notifyListeners();
    });
  }

  private getPathFromUrl(): string {
    return window.location.pathname || '/';
  }

  private notifyListeners(): void {
    this.listeners.forEach(listener => listener(this.currentPath));
  }

  getCurrentPath(): string {
    return this.currentPath;
  }

  navigate(path: string): void {
    if (path !== this.currentPath) {
      this.currentPath = path;
      window.history.pushState({}, '', path);
      this.notifyListeners();
    }
  }

  subscribe(listener: (path: string) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }
}

export const router = new Router();