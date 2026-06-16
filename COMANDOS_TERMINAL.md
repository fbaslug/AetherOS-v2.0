# 🖥 Comandos de Terminal — AetherOS v2.0

Guía completa de los comandos disponibles en la terminal simulada y cómo instalar/desinstalar programas.

---

## 📂 Navegación

| Comando | Descripción | Ejemplo |
|---------|-------------|---------|
| `ls` | Listar archivos | `ls` |
| `ls -la` | Listar con detalles y ocultos | `ls -la` |
| `cd <dir>` | Cambiar de directorio | `cd Documentos` |
| `cd ~` | Ir al home | `cd ~` |
| `cd ..` | Subir un nivel | `cd ..` |
| `pwd` | Mostrar directorio actual | `pwd` |

---

## 📄 Archivos

| Comando | Descripción | Ejemplo |
|---------|-------------|---------|
| `cat <archivo>` | Ver contenido de archivo | `cat readme.txt` |
| `touch <archivo>` | Crear archivo vacío | `touch nuevo.txt` |
| `mkdir <dir>` | Crear directorio | `mkdir proyectos` |
| `mkdir -p <ruta>` | Crear ruta completa | `mkdir -p a/b/c` |
| `rm <archivo>` | Eliminar archivo | `rm viejo.txt` |
| `rm -rf <dir>` | Eliminar directorio con contenido | `rm -rf temp` |
| `rmdir <dir>` | Eliminar directorio vacío | `rmdir vacio` |

---

## 🖥 Sistema

| Comando | Descripción |
|---------|-------------|
| `echo <texto>` | Imprimir texto |
| `uname -a` | Info completa del sistema |
| `whoami` | Usuario actual |
| `hostname` | Nombre del equipo |
| `date` | Fecha y hora |
| `uptime` | Tiempo de actividad |
| `df` | Uso de disco |
| `free` | Uso de memoria |
| `id` | Info del usuario (uid, gid) |
| `neofetch` | Info del sistema con arte ASCII |
| `clear` | Limpiar pantalla |
| `help` | Ver todos los comandos |
| `exit` | Cerrar terminal |

---

## ⌨️ Atajos de Teclado

| Atajo | Acción |
|-------|--------|
| `↑` / `↓` | Navegar historial de comandos |
| `Enter` | Ejecutar comando |
| `Ctrl+C` | Cancelar línea actual |
| `Ctrl+L` | Limpiar pantalla |
| `Home` | Ir al inicio de la línea |

---

## 📦 Gestión de Paquetes

### Actualizar repositorios

```bash
sudo apt update
```

### Ver paquetes disponibles

```bash
apt list
```

### Ver paquetes instalados

```bash
apt list --installed
```

---

## 📥 Instalar Programas

Para instalar un programa se usa el comando `sudo apt install` seguido del nombre del paquete:

```bash
sudo apt install <nombre_del_paquete>
```

La terminal mostrará una animación simulando la descarga e instalación. Al finalizar, **el programa aparecerá como icono en el Escritorio** y podrás abrirlo haciendo clic.

### Instalar nano (Editor de Texto)

```bash
sudo apt install nano
```

- **Icono en escritorio:** 📝
- **Descripción:** Editor de texto ligero con números de línea
- **Atajos dentro de nano:**
  - `Ctrl+O` — Guardar archivo
  - `Ctrl+X` — Salir del editor
  - `Ctrl+K` — Cortar línea
  - `Ctrl+Z` — Deshacer

### Instalar calc (Calculadora)

```bash
sudo apt install calc
```

- **Icono en escritorio:** 🧮
- **Descripción:** Calculadora interactiva con operaciones matemáticas básicas.

---

## 📤 Desinstalar Programas

Para desinstalar un programa se usa el comando `sudo apt remove` seguido del nombre:

```bash
sudo apt remove <nombre_del_paquete>
```

La terminal mostrará la animación de desinstalación. Al finalizar:

- El **icono desaparece del Escritorio**
- Si la ventana del programa estaba abierta, **se cierra automáticamente**

### Desinstalar nano

```bash
sudo apt remove nano
```

### Desinstalar calc

```bash
sudo apt remove calc
```

---

## 📁 Filesystem Virtual

El sistema tiene una estructura de directorios Linux simulada:

```
/
├── home/aether/          ← Tu directorio home (~)
│   ├── Documentos/
│   │   ├── readme.txt
│   │   └── notas.txt
│   ├── Descargas/
│   ├── Escritorio/
│   └── Imagenes/
├── etc/
├── usr/bin/              ← Aquí se instalan los programas
├── var/log/
└── tmp/
```

> **Nota:** El filesystem es virtual (en memoria). Los archivos creados y los programas instalados se pierden al cerrar AetherOS.
