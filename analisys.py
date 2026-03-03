import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Configuração visual dos gráficos
sns.set_theme(style="whitegrid")
plt.rcParams['figure.figsize'] = [10, 6]

def analyze_results(csv_file):
    # 1. Carregar os dados
    df = pd.read_csv(csv_file)
    
    # 2. Cálculo de Métricas por Modelo
    # Assumindo que o CSV tem as colunas: 'model', 'task', 'passed', 'total_attempts'
    metrics = df.groupby('model').agg(
        total_tasks=('task', 'count'),
        successes=('passed', 'sum'),
        avg_attempts=('total_attempts', 'mean')
    ).reset_index()

    # Taxa de Sucesso (%)
    metrics['success_rate'] = (metrics['successes'] / metrics['total_tasks']) * 100

    # 3. Cálculo da Taxa de Recuperação Agêntica (Recovery Rate)
    # Definida como: das tarefas que falharam na 1ª tentativa, quantas passaram no final?
    failed_first = df[df['total_attempts'] > 1]
    recovery = failed_first.groupby('model').agg(
        recovered=('passed', 'sum'),
        total_failed_initially=('task', 'count')
    ).reset_index()
    
    recovery['recovery_rate'] = (recovery['recovered'] / recovery['total_failed_initially']) * 100
    
    final_report = pd.merge(metrics, recovery[['model', 'recovery_rate']], on='model', how='left').fillna(0)

    print("📊 RELATÓRIO DE DESEMPENHO:")
    print(final_report[['model', 'success_rate', 'recovery_rate', 'avg_attempts']])

    # --- GERAÇÃO DE GRÁFICOS ---

    # Gráfico 1: Taxa de Sucesso por Modelo
    plt.figure()
    ax = sns.barplot(x='model', y='success_rate', data=final_report, palette='viridis')
    plt.title('Taxa de Sucesso Global (Success Rate %)')
    plt.ylabel('% de Sucesso')
    plt.ylim(0, 100)
    for p in ax.patches:
        ax.annotate(f'{p.get_height():.1f}%', (p.get_x() + p.get_width() / 2., p.get_height()), 
                    ha='center', va='center', xytext=(0, 9), textcoords='offset points')
    plt.savefig('success_rate_comparison.png')

    # Gráfico 2: Esforço Médio (Tentativas)
    plt.figure()
    sns.boxplot(x='model', y='total_attempts', data=df, palette='magma')
    plt.title('Distribuição de Tentativas por Modelo')
    plt.ylabel('Número de Tentativas')
    plt.savefig('attempts_distribution.png')

    print("\n✅ Gráficos guardados como 'success_rate_comparison.png' e 'attempts_distribution.png'.")

if __name__ == "__main__":
    # Certifique-se de que o ficheiro CSV existe
    analyze_results('resultados_experimento.csv')