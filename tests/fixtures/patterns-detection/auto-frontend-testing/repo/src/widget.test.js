import { render, screen } from 'some-test-utils';

test('renders the widget', () => {
  render(widget());
  screen.getByText('hello');
});
