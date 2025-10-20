import tkinter as tk


class TextProgressBar(tk.Canvas):
  def __init__(
    self, parent, width=300, height=30, bg='black', fg='green', max_value=100, **kwargs
  ):
    super().__init__(
      parent, width=width, height=height, bg=bg, highlightthickness=0, **kwargs
    )
    self.width = width
    self.height = height
    self.fg = fg
    self.max_value = max_value
    self.progress = 0

    # Draw background rectangle
    self.bg_rect = self.create_rectangle(0, 0, width, height, fill=bg, outline='')

    # Draw progress rectangle
    self.progress_rect = self.create_rectangle(0, 0, 0, height, fill=fg, outline='')

    # Add text in center
    self.text = self.create_text(
      width // 2, height // 2, text='0%', fill='white', font=('Arial', 12, 'bold')
    )

  def Reset(self):
    self.SetProgress(0.1)

  def SetProgress(self, value, message=''):
    """Update progress bar value (0 to max_value)."""
    self.progress = min(max(value, 0), self.max_value)
    fill_width = int((self.progress / self.max_value) * self.width)

    # Update bar fill
    self.coords(self.progress_rect, 0, 0, fill_width, self.height)

    # Update text
    percent = int((self.progress / self.max_value) * 100)
    self.itemconfig(self.text, text=f'{percent}%  {message}')
