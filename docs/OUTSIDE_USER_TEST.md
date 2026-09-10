# Outside-user test for v0.1

The automated release gate cannot prove that the handoff makes sense to someone who did not build it. Before calling the release `v0.1`, have at least one person outside the project's development loop run this test without coaching beyond this page.

## Tester task

From a fresh checkout:

```bash
python -m pip install .
oxbow init outside-test
```

The tester should edit `outside-test/HANDOFF.md`, add at least two files of their own, then run:

```bash
oxbow bundle health outside-test
oxbow ship outside-test -o outside-test.oxb.py
python outside-test.oxb.py --verify
python outside-test.oxb.py --tour
python outside-test.oxb.py --cat HANDOFF.md
python outside-test.oxb.py --list
```

Then, without executing the wrapper, inspect it through the installed CLI:

```bash
oxbow verify outside-test.oxb.py
oxbow ls outside-test.oxb.py
```

Finally extract it:

```bash
oxbow extract outside-test.oxb.py -d outside-unpacked
```

The tester should compare the original selected corpus to `outside-unpacked/` and confirm that all source files are present byte-for-byte. The generated manifest will be the one intentional extra file.

## Witness write-back

If the tester uses an AI during the task:

```bash
oxbow witness draft --stream outside-test/witness/stream.json --out witness-prompt.md
```

Give that prompt to the model that just did the work, save the returned JSON as `packet.json`, then:

```bash
oxbow witness validate packet.json
oxbow witness append packet.json --stream outside-test/witness/stream.json
oxbow witness show --stream outside-test/witness/stream.json
```

## Questions to ask the tester afterward

Do not explain the intended answers first.

1. In one sentence, what do you think Oxbow is for?
2. What did you believe `--verify` proved?
3. Did you understand why `.oxb` and `.oxb.py` are different extensions?
4. Did you know what to read first without browsing the entire corpus?
5. At any point did the tool silently omit a file you expected to travel?
6. Was `HANDOFF.md` enough structure, too much, or too little?
7. Did Witness feel optional, or did it look required to use Oxbow?
8. Did Witness v2's richer fields make the record more understandable, or did they mostly feel like form-filling?
9. What was the first confusing command or concept?

Record the tester's actual answers before changing the product. The release gate is not “tester eventually succeeded after explanation”; it is whether the documented interface made the intended object legible.
