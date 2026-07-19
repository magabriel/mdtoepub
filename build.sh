#!/bin/bash
set -uo pipefail

APP_ID="com.github.mdtoepub"
MANIFEST="com.github.mdtoepub.yml"
BUILD_DIR="/tmp/mdtoepub/build-flatpak"
REPO_DIR="/tmp/mdtoepub/repo"
VERSION="${VERSION:-$(grep '^version' pyproject.toml | head -1 | cut -d'"' -f2)}"
BUNDLE="dist/mdtoepub-v${VERSION}.flatpak"

sync_metainfo_version() {
    local xml_file="data/com.github.mdtoepub.metainfo.xml"
    local today
    today=$(date +%Y-%m-%d)
    if [ ! -f "$xml_file" ]; then
        echo "ERROR: $xml_file no encontrado."
        exit 1
    fi
    if ! grep -q '<release version="' "$xml_file"; then
        echo "ERROR: No se encontró tag <release> en $xml_file"
        exit 1
    fi
    sed -i "s|<release version=\"[^\"]*\" date=\"[^\"]*\"|<release version=\"${VERSION}\" date=\"${today}\"|" "$xml_file"
    if ! grep -q "<release version=\"${VERSION}\"" "$xml_file"; then
        echo "ERROR: sync_metainfo_version falló. El metainfo no se actualizó a ${VERSION}."
        exit 1
    fi
}
RUNTIME="org.gnome.Platform"
RUNTIME_VERSION="48"

check_deps() {
    for cmd in flatpak flatpak-builder; do
        if ! command -v "$cmd" &>/dev/null; then
            echo "ERROR: '$cmd' no encontrado. Instálalo con: sudo apt install $cmd"
            exit 1
        fi
    done
}

install_runtime() {
    # Check both user and system installations
    if flatpak list --runtime --user 2>/dev/null | grep -q "${RUNTIME}.Platform.*${RUNTIME_VERSION}" || \
       flatpak list --runtime --system 2>/dev/null | grep -q "${RUNTIME}.Platform.*${RUNTIME_VERSION}"; then
        echo "Runtime ${RUNTIME} ${RUNTIME_VERSION} ya instalado."
        return 0
    fi

    # Ensure flathub user remote exists
    if ! flatpak remotes --user 2>/dev/null | grep -q flathub; then
        echo "Añadiendo repositorio flathub (usuario)..."
        flatpak remote-add --user --if-not-exists flathub \
            https://dl.flathub.org/repo/flathub.flatpakrepo 2>/dev/null || true
    fi

    # Ensure flathub system remote exists as fallback
    if ! flatpak remotes --system 2>/dev/null | grep -q flathub; then
        echo "Añadiendo repositorio flathub (sistema)..."
        flatpak remote-add --system --if-not-exists flathub \
            https://dl.flathub.org/repo/flathub.flatpakrepo 2>/dev/null || true
    fi

    echo "Instalando runtime ${RUNTIME} ${RUNTIME_VERSION}..."
    flatpak install --user -y flathub "${RUNTIME}//${RUNTIME_VERSION}" "${RUNTIME/Platform/Sdk}//${RUNTIME_VERSION}" 2>/dev/null || \
    flatpak install --system -y flathub "${RUNTIME}//${RUNTIME_VERSION}" "${RUNTIME/Platform/Sdk}//${RUNTIME_VERSION}" 2>/dev/null || {
        echo "AVISO: No se pudo instalar el runtime. Si ya lo tienes, ignora este mensaje."
        echo "       El build continuara, pero puede fallar si faltan dependencias."
    }
}

build_app() {
    echo "=== Construyendo ${APP_ID} v${VERSION} ==="
    rm -rf "$BUILD_DIR" "$REPO_DIR" "/tmp/mdtoepub/.flatpak-builder"
    flatpak-builder --user --force-clean --disable-rofiles-fuse \
        --state-dir="/tmp/mdtoepub/.flatpak-builder" \
        --repo="$REPO_DIR" \
        "$BUILD_DIR" \
        "$MANIFEST"
}

create_bundle() {
    mkdir -p dist
    echo "=== Generando bundle ${BUNDLE} ==="
    flatpak build-bundle "$REPO_DIR" "$BUNDLE" "$APP_ID"
    echo ""
    echo "Paquete creado: ${BUNDLE}"
    echo "Tamaño: $(du -h "$BUNDLE" | cut -f1)"
}

cleanup() {
    rm -rf "$BUILD_DIR"
    echo "Build temporal eliminado."
}

show_help() {
    echo "Instalación:"
    echo "  flatpak install --user ${BUNDLE}"
    echo ""
    echo "Ejecución:"
    echo "  flatpak run ${APP_ID}"
    echo ""
    echo "Repo local (para .flatpakref):"
    echo "  ${REPO_DIR}/"
}

set_version() {
    local new_version="$1"
    if [ -z "$new_version" ]; then
        echo "Uso: $0 set-version <version>"
        echo "Ejemplo: $0 set-version 1.6.0"
        exit 1
    fi
    local xml_file="data/com.github.mdtoepub.metainfo.xml"
    local version_file="mdtoepub/_version.py"
    local today
    today=$(date +%Y-%m-%d)
    sed -i "s|^version = \".*\"|version = \"${new_version}\"|" pyproject.toml
    sed -i "s|<release version=\"[^\"]*\" date=\"[^\"]*\"|<release version=\"${new_version}\" date=\"${today}\"|" "$xml_file"
    sed -i "s|^__version__ = \".*\"|__version__ = \"${new_version}\"|" "$version_file"
    git add pyproject.toml "$xml_file" "$version_file"
    git commit -m "chore: bump version to ${new_version}"
    git tag -a "v${new_version}" -m "v${new_version}"
    echo "Versión actualizada a ${new_version} y tag creado."
}

main() {
    case "${1:-all}" in
        all)
            check_deps
            install_runtime
            build_app
            create_bundle
            cleanup
            show_help
            ;;
        build)
            check_deps
            build_app
            ;;
        bundle)
            create_bundle
            ;;
        clean)
            rm -rf /tmp/mdtoepub "$BUNDLE" 2>/dev/null || true
            echo "Limpieza completada."
            ;;
        set-version)
            set_version "$2"
            ;;
        install-local)
        if [ -f "$BUNDLE" ]; then
            echo "=== Instalando bundle: $BUNDLE ==="
            flatpak uninstall --user -y "$APP_ID" 2>/dev/null || true
            flatpak install --user -y "$BUNDLE"
            installed_version=$(flatpak list --app --user 2>/dev/null | grep "$APP_ID" | awk -F'\t' '{print $3}')
            if [ "$installed_version" != "$VERSION" ]; then
                echo ""
                echo "ERROR: Se esperaba instalar v${VERSION} pero flatpak reporta v${installed_version}."
                echo "       El bundle probablemente se generó con una versión anterior."
                echo "       Ejecuta './build.sh' para regenerar el bundle e inténtalo de nuevo."
                exit 1
            fi
            echo "=== v${VERSION} instalada correctamente ==="
        else
            echo "ERROR: $BUNDLE no encontrado. Ejecuta './build.sh' primero."
            exit 1
        fi
        ;;
        reinstall)
        echo "=== Reinstalando bundle: $BUNDLE ==="
        flatpak uninstall --user -y "$APP_ID" 2>/dev/null || true
        if [ -f "$BUNDLE" ]; then
            flatpak install --user -y "$BUNDLE"
            installed_version=$(flatpak list --app --user 2>/dev/null | grep "$APP_ID" | awk -F'\t' '{print $3}')
            if [ "$installed_version" != "$VERSION" ]; then
                echo ""
                echo "ERROR: Se esperaba instalar v${VERSION} pero flatpak reporta v${installed_version}."
                echo "       El bundle probablemente se generó con una versión anterior."
                echo "       Ejecuta './build.sh' para regenerar el bundle e inténtalo de nuevo."
                exit 1
            fi
            echo "=== v${VERSION} instalada correctamente ==="
        else
            echo "ERROR: $BUNDLE no encontrado. Ejecuta './build.sh' primero."
            exit 1
        fi
        ;;
        *)
            echo "Uso: $0 {all|build|bundle|clean|set-version <ver>|install-local|reinstall}"
            exit 1
            ;;
    esac
}

main "$@"
