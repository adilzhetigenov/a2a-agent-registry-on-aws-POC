import React from 'react';
import { render, screen } from '@testing-library/react';
import App from './App';

// Mock the MainPage to avoid complex dependencies in basic test
jest.mock('./pages/MainPage', () => {
  return function MockMainPage() {
    return <div data-testid="main-page">Agent Registry Main Page</div>;
  };
});

test('renders app with main page', () => {
  render(<App />);
  
  // Should show the main page
  expect(screen.getByTestId('main-page')).toBeInTheDocument();
});

test('app component renders without crashing', () => {
  const { container } = render(<App />);
  expect(container).toBeInTheDocument();
});