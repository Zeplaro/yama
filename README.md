
🥔 Python in Maya Done With a Sweet Potato 🥔
===========================================

Yama is a wrapper for `maya.cmds` and `maya.api.OpenMaya`, with consistent object-oriented behavior in relation to maya nodes.

Very similar and very inspired by pymel and cmdx.

Yama is mostly a fancy way for me to store my maya scripts, and a playground to test new tools and allow fast scripting to work how I like it.

## How to use :
_to-do_

## Full Python 3 transition todos :

Once I don't feel the need to support Python 2.7 anymore, here is a list of a couple of things I want to update :

- [ ] Remove unnecessary `object` inheritance to classes.
- [ ] Remove imports of `six` and use of `six.string_types`.
- [ ] Update `super` calls to simpler Python 3 way.
- [ ] Use fstrings EVERYWHERE !
- [ ] Remove Python 2 exception fonctions.
- [ ] Update type hinting to Python 3 way of doing it.
- [ ] Update `nodes.yam` to use `functools.singledispatch` instead of too many if, elifs, else.
- [ ] Update `nodes.Yam` abstract class to use proper Python 3 way of doing an abstract class.
- [ ] Try the walrus operator when usefull.
- [ ] Replace `pass` with `...` when prettier.
- [ ] Use new dictionnary updating method `|=`
- [ ] Make use of positional-only and keyword-only arguments when usefull.
