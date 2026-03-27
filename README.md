`oot` provides a git wrapper that automatically sets the -C flag to `patches.dir`. This, however, does not support autocomplete for git commands. If you wish so, you can define a function in your `.bashrc` as follows:

```bashrc
```bash
oot-git() {
  git -C "$(oot path patches)" "$@"
}
```
```

```
```
```

- Keep in mind that you might need to also pass -c to the inner `oot` command
