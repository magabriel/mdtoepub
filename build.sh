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
    echo "Bundle generado: ${BUNDLE}"
    echo ""
    echo "Para instalar:"
    echo "  ./build.sh install-local"
    echo ""
    echo "O manualmente:"
    echo "  flatpak install --user ${BUNDLE}"
    echo ""
    echo "Para ejecutar:"
    echo "  flatpak run ${APP_ID}"
}

main() {
    case "${1:-all}" in
        all)
            check_deps
            sync_metainfo_version
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
        install-local)
            if [ ! -f "$BUNDLE" ]; then
                echo "ERROR: $BUNDLE no encontrado. Ejecuta './build.sh' primero."
                exit 1
            fi
            echo "=== Instalando bundle: $BUNDLE ==="
            flatpak uninstall --user -y "$APP_ID" 2>/dev/null || true
            flatpak uninstall --system -y "$APP_ID" 2>/dev/null || true
            flatpak install --user -y "$BUNDLE" || {
                echo "ERROR: flatpak install falló."
                exit 1
            }
            installed_version=$(flatpak list --app --user 2>/dev/null | grep "$APP_ID" | awk -F'\t' '{print $3}')
            if [ "$installed_version" != "$VERSION" ]; then
                echo ""
                echo "ERROR: Se esperaba instalar v${VERSION} pero flatpak reporta v${installed_version}."
                echo "       Puede haber una instalación conflictiva o el bundle está desactualizado."
                echo "       Ejecuta './build.sh' para regenerar el bundle e inténtalo de nuevo."
                echo "       Si el problema persiste: flatpak uninstall --user -y --all $APP_ID"
                exit 1
            fi
            echo "=== v${VERSION} instalada correctamente ==="
            ;;
        reinstall)
            echo "=== Reinstalando bundle: $BUNDLE ==="
            flatpak uninstall --user -y "$APP_ID" 2>/dev/null || true
            flatpak uninstall --system -y "$APP_ID" 2>/dev/null || true
            if [ ! -f "$BUNDLE" ]; then
                echo "ERROR: $BUNDLE no encontrado. Ejecuta './build.sh' primero."
                exit 1
            fi
            flatpak install --user -y "$BUNDLE" || {
                echo "ERROR: flatpak install falló."
                exit 1
            }
            installed_version=$(flatpak list --app --user 2>/dev/null | grep "$APP_ID" | awk -F'\t' '{print $3}')
            if [ "$installed_version" != "$VERSION" ]; then
                echo ""
                echo "ERROR: Se esperaba instalar v${VERSION} pero flatpak reporta v${installed_version}."
                echo "       Puede haber una instalación conflictiva o el bundle está desactualizado."
                echo "       Ejecuta './build.sh' para regenerar el bundle e inténtalo de nuevo."
                echo "       Si el problema persiste: flatpak uninstall --user -y --all $APP_ID"
                exit 1
            fi
            echo "=== v${VERSION} instalada correctamente ==="
            ;;
        *)
            echo "Uso: $0 {all|build|bundle|clean|install-local|reinstall}"
            exit 1
            ;;
    esac
}

main "$@"
