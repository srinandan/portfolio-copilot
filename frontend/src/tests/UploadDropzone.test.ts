import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/vue';
import UploadDropzone from '../components/documents/UploadDropzone.vue';

describe('UploadDropzone.vue', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders dropzone instructions and privacy badge', () => {
    render(UploadDropzone);
    expect(screen.getByText('Drop File Here')).toBeDefined();
    expect(screen.getByText(/Validation & Privacy:/i)).toBeDefined();
  });

  it('updates filename display and emits file-selected event when file is selected via input', async () => {
    const { emitted } = render(UploadDropzone);
    const input = screen.getByTestId('file-input') as HTMLInputElement;

    const file = new File(['ticker,qty\nAAPL,10'], 'statement.csv', {
      type: 'text/csv'
    });
    Object.defineProperty(input, 'files', {
      value: [file]
    });

    await fireEvent.change(input);

    expect(screen.getByText('statement.csv')).toBeDefined();
    expect(screen.getByText('CHANGE FILE')).toBeDefined();
    expect(emitted()['file-selected']).toHaveLength(1);
    expect(emitted()['file-selected'][0]).toEqual([file, 'transactions', 'checking_transactions']);
  });

  it('updates target store when document type changes to holdings', async () => {
    const { emitted } = render(UploadDropzone);
    const select = screen.getByTestId('account-type-select') as HTMLSelectElement;
    await fireEvent.update(select, 'holdings');

    const input = screen.getByTestId('file-input') as HTMLInputElement;
    const file = new File(['{"positions":[]}'], 'holdings.json', {
      type: 'application/json'
    });
    Object.defineProperty(input, 'files', {
      value: [file]
    });

    await fireEvent.change(input);
    expect(emitted()['file-selected'][0]).toEqual([file, 'holdings', undefined]);
  });
});
