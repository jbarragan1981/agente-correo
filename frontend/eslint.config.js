// @ts-check
// Configuración ESLint del panel (docs/planes/e0-4-esqueleto-frontend.md §4.2).
const eslint = require('@eslint/js');
const { defineConfig } = require('eslint/config');
const tseslint = require('typescript-eslint');
const angular = require('angular-eslint');

/** Construcciones que abren la puerta a XSS o ejecución dinámica (CA20). */
const sintaxisProhibida = [
  {
    selector: 'MemberExpression[property.name=/^(innerHTML|outerHTML)$/]',
    message: 'Prohibido escribir HTML crudo; usa plantillas Angular o iframe sandbox con srcdoc.',
  },
  {
    selector: 'CallExpression[callee.property.name="insertAdjacentHTML"]',
    message: 'Prohibido insertAdjacentHTML; usa plantillas Angular.',
  },
  {
    selector: 'MemberExpression[object.name="document"][property.name=/^(write|writeln)$/]',
    message: 'Prohibido document.write.',
  },
  {
    selector: 'MemberExpression[property.name=/^bypassSecurityTrust/]',
    message: 'Prohibido bypassSecurityTrust*: el HTML de correos va en iframe sandbox.',
  },
  {
    selector: 'Literal[value=/^(innerHTML|outerHTML|srcdoc)$/]',
    message: 'Prohibido nombrar innerHTML/outerHTML/srcdoc (setProperty, setAttribute, el[...]).',
  },
];

/** Atributos técnicos que no se traducen (regla template/i18n). */
const atributosTecnicos = [
  'autocomplete',
  'class',
  'for',
  'id',
  'name',
  'role',
  'routerLink',
  'routerLinkActive',
  'tabindex',
  'type',
  'value',
  'lang',
  'href',
  'src',
  'aria-hidden',
  'aria-live',
  'aria-atomic',
  'aria-haspopup',
  'aria-controls',
  'aria-describedby',
  'aria-labelledby',
  'appearance',
  'mode',
  'position',
  'color',
  'inputmode',
  'spellcheck',
  'autocapitalize',
  'matTooltipPosition',
  'xPosition',
  'yPosition',
  'data-testid',
  'ngCspNonce',
  'fontIcon',
  'ariaCurrentWhenActive',
];

module.exports = defineConfig([
  {
    ignores: [
      'src/app/core/api/generado/**',
      'dist/**',
      'coverage/**',
      '.angular/**',
      'test-results/**',
      'playwright-report/**',
    ],
  },
  {
    files: ['src/**/*.ts'],
    languageOptions: {
      parserOptions: { projectService: true, tsconfigRootDir: __dirname },
    },
    extends: [
      eslint.configs.recommended,
      tseslint.configs.recommendedTypeChecked,
      tseslint.configs.stylisticTypeChecked,
      angular.configs.tsRecommended,
    ],
    processor: angular.processInlineTemplates,
    rules: {
      '@angular-eslint/directive-selector': [
        'error',
        { type: 'attribute', prefix: ['app', 'vm'], style: 'camelCase' },
      ],
      '@angular-eslint/component-selector': [
        'error',
        { type: 'element', prefix: ['app', 'vm'], style: 'kebab-case' },
      ],
      '@angular-eslint/prefer-on-push-component-change-detection': 'error',
      '@typescript-eslint/no-explicit-any': 'error',
      'no-console': 'error',
      'no-eval': 'error',
      'no-implied-eval': 'error',
      'no-new-func': 'error',
      'no-restricted-syntax': ['error', ...sintaxisProhibida],
      // ErrorApp es el error uniforme de la aplicación (core/errores/error-app.ts).
      '@typescript-eslint/only-throw-error': [
        'error',
        { allow: [{ from: 'file', name: 'ErrorApp', path: 'src/app/core/errores/error-app.ts' }] },
      ],
    },
  },
  {
    files: ['src/**/*.spec.ts', 'src/testing/**/*.ts'],
    rules: {
      '@typescript-eslint/unbound-method': 'off',
    },
  },
  {
    files: ['e2e/**/*.ts', 'playwright.config.ts'],
    extends: [eslint.configs.recommended, tseslint.configs.recommended],
    rules: {
      'no-restricted-syntax': ['error', ...sintaxisProhibida],
    },
  },
  {
    files: ['src/app/**/*.html'],
    extends: [angular.configs.templateRecommended, angular.configs.templateAccessibility],
    rules: {
      '@angular-eslint/template/no-inline-styles': [
        'error',
        { allowNgStyle: false, allowBindToStyle: false },
      ],
      '@angular-eslint/template/i18n': [
        'error',
        {
          checkId: true,
          checkText: true,
          checkAttributes: true,
          ignoreAttributes: atributosTecnicos,
          ignoreTags: ['mat-icon'],
        },
      ],
      '@angular-eslint/template/button-has-type': 'error',
      '@angular-eslint/template/prefer-control-flow': 'error',
      '@angular-eslint/template/prefer-self-closing-tags': 'error',
    },
  },
]);
