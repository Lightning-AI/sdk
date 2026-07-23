import os
from typing import List, Optional

if os.name == "nt":
    import inquirer # import only for windows
    class TerminalMenu:
        def __init__(self, options: List[str], title: Optional[str] = None, **kwargs):
            self.options = options
            self.title = title or "Please select an option:"
            self.chosen_menu_index: Optional[int] = None
        def show(self):
            # generate inquirer questons
            questions = [
                inquirer.List('choice',
                            message=self.title,
                            choices=self.options)
            ]
            answer = inquirer.prompt(questions)
            
            # Keyboard Interrupt
            if not answer or 'choice' not in answer:
                self.chosen_menu_index = None
                return
            
            self.chosen_menu_index = self.options.index(answer['choice'])
else:
    from simple_term_menu import TerminalMenu