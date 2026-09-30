# Local-Only Files

이 저장소에는 역분석 원본을 넣지 않는다.

권장 로컬 구조:

```text
local/
├── apk/
│   ├── original.apk
│   └── patched/
├── il2cpp/
│   ├── libil2cpp.so
│   └── global-metadata.dat
├── ghidra/
│   └── HeroesProject/
└── work/
```

Git 저장소 루트에 로컬 작업 디렉터리를 둘 경우 다음은 반드시 `.gitignore`로 제외한다.
