# Compilers Directory

Place PIC assembler executables in the appropriate subdirectory.
The IDE will search this folder **first** before scanning system-wide install locations.

## Directory Structure

```
compilers/
├── mpasm/          ← Place mpasmx.exe (or mpasm.exe) here
├── xc8-pic-as/     ← Place pic-as.exe here  (from MPLAB XC8)
├── gpasm/          ← Place gpasm.exe here    (from gputils)
└── README.md       ← This file
```

## How It Works

1. Copy the compiler executable (and any required support files) into the matching subdirectory.
2. Launch the IDE — it will auto-detect the local compiler on startup.
3. To switch compilers, go to **Tools → Assembler Settings** and select the desired assembler type.

## Required Files

### MPASM / mpasmx

| File | Required | Notes |
|---|---|---|
| `mpasmx.exe` or `mpasm.exe` | **Yes** | Main assembler executable |
| `*.inc` header files | Optional | Device include files (e.g. `p18f4550.inc`) |

### XC8 pic-as

| File | Required | Notes |
|---|---|---|
| `pic-as.exe` | **Yes** | MPLAB XC8 PIC assembler |
| XC8 support files | Recommended | The full XC8 toolchain is recommended |

### gpasm (gputils)

| File | Required | Notes |
|---|---|---|
| `gpasm.exe` | **Yes** | Open-source gputils assembler |
| `*.inc` header files | Optional | Shipped with gputils |

## Download Links

- **MPASM**: Included with [MPLAB X IDE](https://www.microchip.com/mplab/mplab-x-ide) or legacy MPLAB IDE v8.x
- **XC8 / pic-as**: [MPLAB XC8 Compiler](https://www.microchip.com/en-us/tools-resources/develop/mplab-xc-compilers/xc8)
- **gputils / gpasm**: [gputils on SourceForge](https://gputils.sourceforge.io/)
